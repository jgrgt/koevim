import re
import itertools
import compiler
from collections import defaultdict
import functools

indentre = re.compile("^([ ]*)[^ ]")
def getIndent(line):
    match = indentre.match(line)
    if match:
        return match.group(1)
    return ""

class Visitor:
    def __init__(self):
        self.info = dict()
    def visitFunction(self, node):
        self.info['name'] = node.name
        self.info['doc'] = node.doc
        deflen = len(node.defaults)
        if deflen > 0:
            self.info['argnames'] = node.argnames[:(-1 * deflen)]
            self.info['kwargnames'] = node.argnames[(-1 * deflen):]
        else:
            self.info['argnames'] = node.argnames
            self.info['kwargnames'] = list()
        self.info['defaults'] = node.defaults

class Argument(object):
    param = None
    type = None

class DocString(object):
    paramre = re.compile("^@param ([^:]*):[ ]*(.*)$")
    typere = re.compile("^@type ([^:]*):[ ]*(.*)$")
    returnre = re.compile("^@return[s]?[ ]?:[ ]*(.*)$")
    rtypere = re.compile("^@rtype[ ]?:[ ]*(.*)$")
    returnarg = "___return"

    def __init__(self, doclines, args, kwargs, defaults, marker):
        self.argdict = defaultdict(Argument)
        self.doclines = doclines
        self.args = args
        self.kwargs = kwargs
        self.defaults = defaults
        self.marker = marker
        self.parse()

    def parse(self):
        before = list()
        atlines = list()
        after = list()

        BEFORE, ATLINES = range(1, 3)
        state = BEFORE

        for line in self.doclines:
            isparamline = self.isParamLine(line)
            if state == BEFORE:
                if not isparamline:
                    before.append(line)
                else:
                    state = ATLINES
                    atlines.append(line)
            elif state == ATLINES:
                if not isparamline:
                    # Asume this line is an after line
                    after.append(line)
                else:
                    atlines.append(line)
                    # Reset after, move everything to before
                    before.extend(after)
                    after = list()

        self.before = before
        self.parseAtLines(atlines)
        self.after = after

    def isParamLine(self, line):
        for s in ('@param', '@type', '@return', '@rtype'):
            if line.startswith(s):
                return True
        return False

    def parseAtLines(self, atlines):
        for line in atlines:
            sline = line.lstrip()
            if sline.startswith('@param'):
                name, descr = self.paramre.match(sline).groups()
                self.argdict[name].param = descr
            elif sline.startswith('@type'):
                name, descr = self.typere.match(sline).groups()
                self.argdict[name].type = descr
            elif sline.startswith('@return'):
                name = self.returnarg
                descr = self.returnre.match(sline).groups()
                self.argdict[name].param = descr
            elif sline.startswith('@rtype'):
                name = self.returnarg
                descr = self.rtypere.match(sline).groups()
                self.argdict[name].type = descr

    def getAtLines(self):
        ret = list()
        for arg in itertools.chain(self.args, self.kwargs):
            ret.append("@param %s: %s" % (arg, self.argdict[arg].param or ''))
            ret.append("@type %s: %s" % (arg, self.argdict[arg].type or ''))
        ret.append("@return: %s" % self.argdict[self.returnarg].param or '')
        ret.append("@rtype: %s" % self.argdict[self.returnarg].type or '')
        return ret

    def getLines(self):
        ret = WhitespaceFilter(IndentedLines(self.before, self.doclines.indentation))
        ret.extend(self.getAtLines())
        ret.extend(self.after)
        if not ret[0].strip():
            ret[0] = self.marker
        else:
            ret.insert(0, self.marker)

        if not ret[-1].strip():
            ret[-1] = self.marker
        else:
            ret.append(self.marker)
        return ret.getIndentedLines()

class IndentedLines(list):
    def __init__(self, lines, indentation=None):
        list.__init__(self, lines)
        self.indentation = indentation or ""

    def toString(self, indentation=None):
        return "\n".join(self.getIndentedLines(indentation))

    def getIndentedLines(self, indentation=None):
        if indentation is None:
            indentation = self.indentation
        return ["%s%s" % (indentation, line) for line in self]

def WhitespaceFilter(indentedLines):
    """
    Attempt at the decorator pattern.

    Not quite like it should be.
    """
    func = indentedLines.getIndentedLines
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        return [line.rstrip() for line in func(*args, **kwargs)]

    indentedLines.getIndentedLines = decorator
    return indentedLines

class AutoIndentedLines(IndentedLines):
    def __init__(self, lines):
        if not len(lines):
            indent = ""
            cleanedLines = lines
        else:
            indent = ""
            for line in lines:
                if line.strip():
                    indent = getIndent(line)
                    break

            l = len(indent)

            def clean(line):
                # No regex, happy now, ikke?
                if line[:l] == indent:
                    return line[l:] or "" # If line is only indentation, line[:l] returns None
                else:
                    return line

            cleanedLines = [clean(line) for line in lines]

        IndentedLines.__init__(self, cleanedLines, indent)

def GenerateDocString(buf, selected, sel_start, sel_stop):
    fundef = AutoIndentedLines(selected)

    # Search for a docstring
    marker = None
    for m in ('"""', "'''"):
        if '"""' in buf[sel_stop]:
            marker = '"""'
    docstring_begin = docstring_end = sel_stop

    if marker:
        # Find the docstring end
        if buf[sel_stop].count(marker) > 1:
            doc = AutoIndentedLines([buf[sel_stop]])
            docstring_end = docstring_begin + 1
        else:
            # Search for max 100 lines for the end of the docstring
            for x in range(1, 100):
                end = sel_stop + x
                if end > len(buf) or marker in buf[end]:
                    lines = list(buf[sel_stop:(end + 1)])
                    doc = AutoIndentedLines(lines)
                    docstring_end = end + 1
                    break
    else:
        marker = '"""'
        defaultDoc = ['"""', 'Short description here', '"""']
        indentation = "%s    " % fundef.indentation
        doc = IndentedLines(defaultDoc, indentation=indentation)
    # Add pass
    # Warning: won't work with tab-indentation TODO
    indentation = doc.indentation
    passline = IndentedLines(["pass"], indentation)

    # Create an f with no indentation for the function def
    # and 4 spaces of indentation for the docstring and pass
    indentation = "    "
    f = "%s\n%s\n%s" % (fundef.toString(""), doc.toString(indentation), passline.toString(indentation))
    ast = compiler.parse(f)
    v = Visitor()
    compiler.walk(ast, v)
    info = v.info
    cleandoc = AutoIndentedLines(info['doc'].splitlines())
    cleandoc.indentation = doc.indentation

    # Filter out self:
    argnames = info['argnames']
    if argnames[0] == 'self':
        argnames = argnames[1:]

    buf[docstring_begin:docstring_end] = DocString(cleandoc, argnames, info['kwargnames'], info['defaults'], marker).getLines()


if __name__ == "__main__":
    def generate(buffer):
        GenerateDocString(buffer, [buffer[0]], 0, 1)

        print "\n".join(buffer)

    buffer1 = ['    def foo(bar, nieuw, baz=None):',
        '        """',
        '        dit is ervoor',
        '',
        '        @param bar: ',
        '        @type bar: dsf',
        '        @param baz: ',
        '        @type baz: re',
        '        @return: ',
        '        @rtype: None',
        '',
        '        en erna',
        '        """',
        '        return True'
    ]

    generate(buffer1)

    buffer2 = [
        'def spam(self):',
        '    return False',
    ]

    generate(buffer2)

    buffer3 = [
        'def eggs(self, white, yolk):',
        '    """This is a oneline docstring"""',
        '    return False',
    ]

    generate(buffer3)
