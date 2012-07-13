if exists("b:loaded_py_ftplugin_koevim")
  finish
endif
let b:loaded_py_ftplugin_koevim = 1

python << EOF
import vim

import os
import sys
vimpath = os.path.expanduser(os.path.join("~", ".vim", "python"))
sys.path.append(vimpath)

from koevim import GenerateDocString

def SetBreakpoint():
    nLine = int( vim.eval( 'line(".")'))

    strLine = vim.current.line
    strWhite = re.search( '^(\s*)', strLine).group(1)

    vim.current.buffer.append(
       "%(space)spdb.set_trace() %(mark)s Breakpoint %(mark)s" %
         {'space':strWhite, 'mark': '#' * 30}, nLine - 1)

    for strLine in vim.current.buffer:
        if strLine == "import pdb":
            break
    else:
        vim.current.buffer.append( 'import pdb', 0)
        vim.command( 'normal j1')

vim.command( 'map <f7> :py SetBreakpoint()<cr>')

def RemoveBreakpoints():
    nCurrentLine = int( vim.eval( 'line(".")'))

    nLines = []
    nLine = 1
    for strLine in vim.current.buffer:
        if strLine == 'import pdb' or strLine.lstrip()[:15] == 'pdb.set_trace()':
            nLines.append( nLine)
        nLine += 1

    nLines.reverse()

    for nLine in nLines:
        vim.command( 'normal %dG' % nLine)
        vim.command( 'normal dd')
        if nLine < nCurrentLine:
            nCurrentLine -= 1

    vim.command( 'normal %dG' % nCurrentLine)

vim.command( 'map <s-f7> :py RemoveBreakpoints()<cr>')


def VimGenerateDocString():
    # Requires a selection
    buf = vim.current.buffer
    sel_start, col = buf.mark("<")
    sel_stop, col = buf.mark(">")
    GenerateDocString(buf, vim.current.range, sel_start, sel_stop)

vim.command('map <c-f7> :py VimGenerateDocString()<cr>')
EOF
