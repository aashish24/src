##   Copyright (C) 2004 University of Texas at Austin
##  
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2 of the License, or
##   (at your option) any later version.
##  
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.
##  
##   You should have received a copy of the GNU General Public License
##   along with this program; if not, write to the Free Software
##   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os, re, glob, string, types, pwd, shutil
import cStringIO, token, tokenize, cgi, sys, keyword
import rsfconf, rsfdoc, rsfprog, latex2wiki, vplot2eps

import SCons

# The following adds all SCons SConscript API to the globals of this module.
version = map(int,string.split(SCons.__version__,'.'))
if version[1] >= 97 or (version[1] == 96 and version[2] >= 90):
    from SCons.Script import *
else:
    import SCons.Script.SConscript
    globals().update(SCons.Script.SConscript.BuildDefaultGlobals())

#############################################################################
# CONFIGURATION VARIABLES
#############################################################################

bibtex      = WhereIs('bibtex')
acroread    = WhereIs('acroread')
pdfread     = acroread or WhereIs('kpdf') or WhereIs('xpdf') or WhereIs('gv')
pdftops     = WhereIs('pdftops')
epstopdf    = WhereIs('epstopdf')
if epstopdf:
    latex       = WhereIs('pdflatex')
    ressuffix = '.pdf'
else:
    latex       = WhereIs('latex')
    ressuffix = '.eps'
fig2dev     = WhereIs('fig2dev')
latex2html  = WhereIs('latex2html')
pdf2ps      = WhereIs('pdf2ps')
ps2eps      = WhereIs('ps2epsi')
pstoimg     = WhereIs('pstoimg')
mathematica = WhereIs('mathematica')
if mathematica:
    mathematica = WhereIs('math')
matlab      = WhereIs('matlab')

vpsuffix  = '.vpl'
pssuffix  = '.eps'
itype = os.environ.get('IMAGE_TYPE','png')

rerun = re.compile(r'\bRerun')

# directory tree for executable files
top = os.environ.get('RSFROOT')
bindir = os.path.join(top,'bin')
libdir = os.path.join(top,'lib')
incdir = os.path.join(top,'include')
figdir = os.environ.get('RSFFIGS',os.path.join(top,'figs'))

#############################################################################
# UTILITY FUNCTIONS
#############################################################################

def mkdir(dir):
    'Recursive directory making'
    while os.path.basename(dir) == '.':
        dir = os.path.dirname(dir)
    if not os.path.isdir(dir):
        mkdir(os.path.dirname(dir))        
        os.mkdir(dir)
    return dir

#############################################################################
# REGULAR EXPRESSIONS
#############################################################################

isplot = re.compile(r'^[^%]*\\(?:side|full)?plot\*?\s*(?:\[[htbp]+\])?' \
                    '\{([^\}]+)')
ismplot = re.compile(r'^[^%]*\\multiplot\*?\s*(?:\[[htbp]+\])?' \
                     '\{[^\}]+\}\s*\{([^\}]+)')
isfig  = re.compile(r'^[^%]*\\includegraphics\s*(\[[^\]]*\])?\{([^\}]+)')
isbib = re.compile(r'\\bibliography\s*\{([^\}]+)')
linput = re.compile(r'[^%]\\(?:lst)?input(?:listing\[[^\]]+\])?\s*\{([^\}]+)')
chdir = re.compile(r'[^%]*\\inputdir\s*\{([^\}]+)')
subdir = re.compile(r'\\setfigdir{([^\}]+)')
beamer = re.compile(r'\\documentclass[^\{]*\{beamer\}')
hastoc =  re.compile(r'\\tableofcontents')
figure = re.compile(r'\\contentsline \{figure\}\{\\numberline \{([^\}]+)')
subfigure = re.compile(r'\\contentsline \{subfigure\}\{\\numberline \{\(([\w])')
logfigure = re.compile(r'\s*\<use ([^\>]+)')
suffix = re.compile('\.[^\.]+$')
cwpslides = re.compile(r'\\documentclass[^\{]*\{cwpslides\}')

#############################################################################
# CUSTOM BUILDERS
#############################################################################

def latify(target=None,source=None,env=None):
    "Add header and footer to make a valid LaTeX file"
    tex = open(str(source[0]),'r')
    ltx = open(str(target[0]),'w')
    lclass = env.get('lclass','geophysics')
    if lclass == 'segabs':
        size = '11pt'
    else:
        size = '12pt'
    options = env.get('options',size)
    if not options:
        options = size
    ltx.write('%% This file is automatically generated. Do not edit!\n')
    ltx.write('\\documentclass[%s]{%s}\n\n' % (options,lclass))
    use = env.get('use')
    resdir = env.get('resdir','Fig')
    include = env.get('include')
    if use:
         if type(use) is not types.ListType:
              use = [use]
         for package in use:
              options = re.match(r'(\[[^\]]*\])\s*(\S+)',package)
              if options:
                   ltx.write('\\usepackage%s{%s}\n' % options.groups())
              else:
                   ltx.write('\\usepackage{%s}\n' % package)
         ltx.write('\n')
    if include:
        ltx.write(include+'\n\n')
    if lclass in ('geophysics','segabs','georeport'):
        ltx.write('\\setfigdir{%s}\n\n' % resdir)
    ltx.write('\\begin{document}\n')
    for line in tex.readlines():
        ltx.write(line)
    ltx.write('\\end{document}\n')
    ltx.close()
    return 0

def latex_emit(target=None, source=None, env=None):
    tex = str(source[0])    
    stem = suffix.sub('',tex)
    target.append(stem+'.aux')
    target.append(stem+'.log')
    contents = source[0].get_contents()
    if isbib.search(contents):
        target.append(stem+'.bbl')
        target.append(stem+'.blg')
    if hastoc.search(contents):
        target.append(stem+'.toc')
    if beamer.search(contents):
        target.append(stem+'.nav')
        target.append(stem+'.out')
        target.append(stem+'.snm')
    if cwpslides.search(contents):
        target.append(stem+'.nav')
        target.append(stem+'.out')
        target.append(stem+'.snm')
        target.append(stem+'.toc')
    return target, source

def latex2dvi(target=None,source=None,env=None):
    "Convert LaTeX to DVI/PDF"
    tex = str(source[0])
    dvi = str(target[0])
    stem = suffix.sub('',dvi)    
    run = string.join([latex,tex],' ')
    # First latex run
    if os.system(run):
        return 1
    # Check if bibtex is needed
    aux = open(stem + '.aux',"r")    
    for line in aux.readlines():
        if re.search("bibdata",line):
            os.system(string.join([bibtex,stem],' '))
            os.system(run)
            os.system(run)
            break
        elif re.search("beamer@",line):
            os.system(run)
            os.system(run)
            break
    aux.close()
    # (Add makeindex later)
    # Check if rerun is needed
    for i in range(3): # repeat 3 times at most
        done = 1
        log = open(stem + '.log',"r")
        for line in log.readlines():
            if rerun.search(line):
                done = 0
                break
        log.close()
        if done:
            break
        os.system(run)
    return 0

loffigs = {}

def listoffigs(target=None,source=None,env=None):
    "Copy figures"
    global loffigs
    
    pdf = str(source[0])
    stem = suffix.sub('',pdf)   

    try:
        lof = open(stem+'.lof')
        log = open(stem+'.log')
    except:
        return target, source

    figs = []
    for line in lof.readlines():
        fig = figure.match(line)
        if fig:
            figs.append(fig.group(1))
        else:
            subfig = subfigure.match(line)
            if subfig:
                last = figs.pop()
                if re.search('[a-z]$',last):
                    figs.append(last)
                    figs.append(last[:-1]+subfig.group(1))
                else:
                    figs.append(last+subfig.group(1))
    lof.close()

    for line in log.readlines():
        fil = logfigure.match(line)
        if fil:
            fig = figs.pop(0)
            for ext in ('eps','pdf'):
                src = suffix.sub('.'+ext,fil.group(1))
                dst = '%s-Fig%s.%s' % (stem,fig,ext)

                loffigs[dst]=src
                target.append(dst)
                env.Precious(dst)
    log.close()

    return target, source

def copyfigs(target=None,source=None,env=None):
     "Copy figures"
     for fig in target[1:]:
          dst = str(fig)
          src = loffigs[dst]
          try:
               shutil.copy(src,dst)
          except:
               sys.stderr.write('Cannot copy %s' % src)
     return 0

def latex2mediawiki(target=None,source=None,env=None):
    "Convert LaTeX to MediaWiki"
    texfile = str(source[0])
    tex = open(texfile,"r")
    bblfile = re.sub('\.[^\.]+$','.bbl',texfile)
    print bblfile
    try:
        bbl = open(bblfile,"r")
        latex2wiki.parse_bbl(bbl)
        bbl.close()
    except:
        pass
    wiki = open(str(target[0]),"w")
    latex2wiki.convert(tex,wiki)
    wiki.close()
    tex.close()
    return 0

def pstexpen(target=None,source=None,env=None):
    "Convert vplot to EPS"
    vpl = str(source[0])
    eps = str(target[0])

    try:
        vplot2eps.convert(vpl,eps)
    except:
        return 1
    return 0

def uses(target=None,source=None,env=None):
    "Collect RSF program uses"
    project = os.path.dirname(str(source[0]))

    out = open(str(target[0]),"w")
    os.chdir(project)

    sin, sout, serr = os.popen3('scons -s .sf_uses')
    sin.close()

    progs = sout.read()
    sout.close()

    status = serr.read()
    serr.close() 

    if status:
        sys.stderr.write('No uses found in %s: %s\n' % (project,status))
    elif string.find(progs,'scons') < 0:
        tree = env.get('tree')
        doc = map(lambda prog:
                  'rsfdoc.progs["%s"].use("%s","%s","%s")' %
                  (prog,tree[1],tree[2],project),string.split(progs))
        out.write(string.join(doc,'\n') + '\n')
        
    os.chdir('..')
    out.close()
    return 0

_KEYWORD = token.NT_OFFSET + 1
_TEXT    = token.NT_OFFSET + 2

_colors = {
     token.NUMBER:       '#0080C0',
     token.OP:           '#0000C0',
     token.STRING:       '#004080',
     tokenize.COMMENT:   '#008000',
     token.NAME:         '#000000',
     token.ERRORTOKEN:   '#FF8080',
     _KEYWORD:           '#C00000',
     _TEXT:              '#000000',
     'Fetch':            '#0000C0',
     'Flow':             '#0000C0',
     'Plot':             '#0000C0',
     'Result':           '#C00000'
     }

_styles = {
     token.NUMBER:       'number',
     token.OP:           'op',
     token.STRING:       'string',
     tokenize.COMMENT:   'comment',
     token.NAME:         'name',
     token.ERRORTOKEN:   'error',
     _KEYWORD:           'keyword',
     _TEXT:              'text',
     'Fetch':            'fetch',
     'Flow':             'flow',
     'Plot':             'plot',
     'Result':           'result'
     }

_pos = 0


def _proglink(name):
    link = '<a href="/RSF/%s.html">%s</a>' % (rsfdoc.progs[name].name, name)
    return link

dataserver = 'ftp://egl.beg.utexas.edu'

def _datalink(name):
    global dataserver
    link = '<a href="%s/%s">%s</a>' % (dataserver,name,name)
    return link
 
def colorize(target=None,source=None,env=None):
     "Colorize python source"
     py = str(source[0])
     html = str(target[0])

     src = open(py,'r').read()
     raw = string.strip(string.expandtabs(src))

     out = open(html,'w')
     out.write('''
     <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN">
     <html>
     <head>
     <title>%s</title>
     <style type="text/css">
     div.progs {
     background-color: #DCE3C4;
     border: thin solid black;
     padding: 1em;
     margin-left: 2em;
     margin-right: 2em; }
     div.dsets {
     background-color: #E3C4DC;
     border: thin solid black;
     padding: 1em;
     margin-left: 2em;
     margin-right: 2em; }
     div.scons {
     background-color: #FFF8ED;
     border: thin solid black;
     padding: 1em;
     margin-left: 2em;
     margin-right: 2em; }
     ''' % py)
     for style in _styles.keys():
          out.write('.%s { color: %s; }\n' % (_styles[style],_colors[style])) 
     out.write('''</style>
     </head>
     <body>
     <div>
     <a href="paper_html/paper.html"><img width="32" height="32"
     align="bottom" border="0" alt="up" src="paper_html/icons/up.%s"></a>
     <a href="paper.pdf"><img src="paper_html/icons/pdf.%s" alt="[pdf]"
     width="32" height="32" border="0"></a>
     </div>
     <div class="scons">
     <table><tr><td>
     ''' % (itype,itype))

     # store line offsets in self.lines
     lines = [0, 0]
     _pos = 0
     while 1:
          _pos = string.find(raw, '\n', _pos) + 1
          if not _pos: break
          lines.append(_pos)
     lines.append(len(raw))


     # parse the source and write it
     _pos = 0
     text = cStringIO.StringIO(raw)
     out.write('<pre><font face="Lucida,Courier New">')

     def call(toktype, toktext, (srow,scol), (erow,ecol), line):
          global _pos
          
          # calculate new positions
          oldpos = _pos
          newpos = lines[srow] + scol
          _pos = newpos + len(toktext)
    
          # handle newlines
          if toktype in [token.NEWLINE, tokenize.NL]:
               out.write("\n")
               return

          # send the original whitespace, if needed
          if newpos > oldpos:
               out.write(raw[oldpos:newpos])

          # skip indenting tokens
          if toktype in [token.INDENT, token.DEDENT]:
               _pos = newpos
               return

          # map token type to a color group
          if token.LPAR <= toktype and toktype <= token.OP:
               toktype = token.OP
          elif toktype == token.NAME and keyword.iskeyword(toktext):
               toktype = _KEYWORD
          elif toktype == token.NAME and toktext in _colors.keys():
               toktype = toktext
               
          style = _styles.get(toktype, _styles[_TEXT])
 
          # send text
          out.write('<span class="%s">' % style)
          out.write(cgi.escape(toktext))
          out.write('</span>')

     try:
          tokenize.tokenize(text.readline, call)
     except tokenize.TokenError, ex:
          msg = ex[0]
          line = ex[1][0]
          out.write("<h3>ERROR: %s</h3>%s\n" % (msg, raw[lines[line]:]))
          return 1

     out.write('</font></pre></table>')

     cwd = os.getcwd()
     os.chdir(os.path.dirname(py))

     #     (status,progs) = commands.getstatusoutput('scons -s .sf_uses')

     for case in ('uses','data'):
         sin, sout, serr = os.popen3('scons -s .sf_'+case)
         sin.close()
         progs = sout.read()
         sout.close()
         status = serr.read()
         serr.close() 
     
         if not status:
             items = string.split(progs)
             if items:
                 if case=='uses':
                     out.write('</div><p><div class="progs">')
                     out.write(rsfdoc.multicolumn(items,_proglink))
                 else:
                     while 'PRIVATE' in items:
                         items.remove('PRIVATE')
                     out.write('</div><p><div class="dsets">')
                     out.write(rsfdoc.multicolumn(items,_datalink))
 
     out.write('''
     </div>
     </body>
     </html>
     ''')

     os.chdir(cwd)
     return 0


plotoption = {}

def eps2png(target=None,source=None,env=None):
     png = str(target[0])
     eps = str(source[0])
     option = plotoption.get(os.path.basename(eps),'')
     command =  'PAPERSIZE=ledger %s %s -out %s' \
               + ' -type %s -interlaced -antialias -crop a %s'
     command = command % (pstoimg,eps,png,itype,option)
     print command
     os.system(command)
     return 0

def dummy(target=None,source=None,env=None):
     tex = open(str(target[0]),'w')
     tex.write('%% This file is automatically generated. Do not edit!\n')

     user = os.getuid()
     name = pwd.getpwuid(user)[4]

     tex.write('\\author{%s}\n' % name)
     tex.write('\\title{Dummy paper}\n\n\maketitle\n')
     dirold = ''
     for src in source:
         fig = str(src)
         plt = os.path.splitext(os.path.basename(fig))[0]
         plt2 = string.replace(plt,'_','\_')
         dir = os.path.split(os.path.split(fig)[0])[0]
         if dir != dirold:
             tex.write('\n\\section{%s}\n' % dir)
             tex.write('\\inputdir{%s}\n\n' % dir)
             dirold = dir
         tex.write('\\plot{%s}{width=\\textwidth}{%s/%s} ' % (plt,dir,plt2))
         tex.write('\\clearpage\n')
     tex.close()    
     return 0

Latify = Builder(action = Action(latify,
                                 varlist=['lclass','options','use',
                                          'include','resdir']),
                 src_suffix='.tex',suffix='.ltx')
Pdf = Builder(action=Action(latex2dvi,varlist=['latex']),
              src_suffix='.ltx',suffix='.pdf',emitter=latex_emit)
Wiki = Builder(action=Action(latex2mediawiki),src_suffix='.ltx',suffix='.wiki')
Figs = Builder(action=Action(copyfigs),
               src_suffix='.pdf',emitter=listoffigs)

if pdfread:
    Read = Builder(action = pdfread + " $SOURCES",
                   src_suffix='.pdf',suffix='.read')
    Print = Builder(action =
                    'cat $SOURCES | %s -toPostScript | lpr' % pdfread,
                    src_suffix='.pdf',suffix='.print')

Build = Builder(action = Action(pstexpen),
                src_suffix=vpsuffix,suffix=pssuffix)
Uses = Builder(action = Action(uses),varlist=['tree'])

if epstopdf:
    epstopdf = 'LD_LIBRARY_PATH=%s %s' % (os.environ.get('LD_LIBRARY_PATH',''),
                                          epstopdf)
    PDFBuild = Builder(action = epstopdf + " $SOURCES",
		       src_suffix=pssuffix,suffix='.pdf')

if fig2dev:
    XFig = Builder(action = fig2dev + ' -L pdf -p dummy $SOURCES $TARGETS',
                   suffix='.pdf',src_suffix='.fig')


if pstoimg:
     PNGBuild = Builder(action = Action(eps2png),
                        suffix='.'+itype,src_suffix=pssuffix)

if pdftops:
    PSBuild = Builder(action = pdftops + ' -eps $SOURCE $TARGET',
                      suffix=pssuffix,src_suffix='.pdf')
elif acroread and ps2eps:
    PSBuild = Builder(action = '%s -toPostScript -size ledger -pairs $SOURCE'
                      ' junk.ps && %s junk.ps $TARGET && rm junk.ps' % \
                      (acroread,ps2eps),
                      suffix=pssuffix,src_suffix='.pdf')
elif pdf2ps:
    PSBuild = Builder(action = pdf2ps + ' $SOURCE $TARGET',
                      suffix=pssuffix,src_suffix='.pdf')

if latex2html:
    l2hdir = os.environ.get('LATEX2HTML','')
    inputs = os.environ.get('TEXINPUTS','')
    if l2hdir:
        init = '-init_file ' + os.path.join(l2hdir,'.latex2html-init')
        css0 = os.path.join(l2hdir,'style.css')
        icons0 = os.path.join(l2hdir,'icons')
    else:
        init = ''

    HTML = Builder(action = 'TEXINPUTS=%s LATEX2HTMLSTYLES=%s/perl %s '
                   '-debug $SOURCE -dir $TARGET.dir -image_type %s %s' %
                   (inputs,l2hdir,latex2html,itype,init),src_suffix='.ltx')

if mathematica and epstopdf:
     Math = Builder(action = 'DISPLAY=" " nohup %s -batchoutput '
                    '< $SOURCE >& /dev/null > /dev/null && '
                    '%s junk_ma.eps -o=$TARGET && rm junk_ma.eps' %
                    (mathematica,epstopdf),
                    suffix='.pdf',src_suffix='.ma')
if matlab and epstopdf:
    matlabpath = os.environ.get('MATLABPATH')
    if matlabpath:
        matlabpath = string.join([matlabpath,'Matlab'],':')
    else:
        matlabpath = 'Matlab'
    Matlab = Builder(action = 'MATLABPATH=%s DISPLAY=" " nohup %s -nojvm '
                     '< $SOURCE >& /dev/null > /dev/null && '
                     '%s junk_ml.eps -o=$TARGET && rm junk_ml.eps' %
                     (matlabpath,matlab,epstopdf),
                     suffix='.pdf',src_suffix='.ml')
     
Color = Builder(action = Action(colorize),suffix='.html')
                   
#############################################################################
# CUSTOM SCANNERS
#############################################################################

def latexscan(node,env,path):
    top = str(node)
    if top[-4:] != '.tex':
        return []
    contents = node.get_contents()
    inputs = filter(os.path.isfile,
                    map(lambda x: x+('.tex','')[os.path.isfile(x)],
                        linput.findall(contents)))
    inputs.append(str(node))
    resdir = env.get('resdir','Fig')
    inputdir = env.get('inputdir','.')
    plots = []
    for file in inputs:
        inp = open(file,'r')
        for line in inp.readlines():            
            dir  = chdir.search(line)
            if dir:
                inputdir = dir.group(1)
            dir = subdir.search(line)
            if dir:
                resdir = dir.group(1)
            resdir2 = os.path.join(inputdir,resdir)
            
            check = isplot.search(line)
            if check:
                 plot = check.group(1)
                 plot = string.replace(plot,'\_','_')
                 plots.append(os.path.join(resdir2,plot + ressuffix))
                 if re.search('angle=90',line):
                      plotoption[plot+pssuffix] = '-flip r90'

            
            check = ismplot.search(line)
            if check:
                 mplot = check.group(1)
                 mplot = string.replace(mplot,'\_','_')
                 for plot in string.split(mplot,','):
                     plots.append(os.path.join(resdir2,plot + ressuffix))
                     if re.search('angle=90',line):
                         plotoption[plot+pssuffix] = '-flip r90'

            check = isfig.search(line)
            if check:
                 plot = check.group(2)
                 if plot[-len(ressuffix):] != ressuffix:
                     plot = plot + ressuffix
                 plots.append(plot)
  
        inp.close()
    bibs = []
    for bib in isbib.findall(contents):
        for file in string.split(bib,','):
            file = file+'.bib'
            if os.path.isfile(file):
                bibs.append(file)
    return plots + inputs + bibs

LaTeX = Scanner(name='LaTeX',function=latexscan,skeys=['.tex','.ltx'])

#############################################################################

class TeXPaper(Environment):
    def __init__(self,**kw):
        apply(Environment.__init__,(self,),kw)
        opts = Options(os.path.join(libdir,'rsfconfig.py'))
        rsfconf.options(opts)
        opts.Update(self)
        self.Append(ENV={'XAUTHORITY':
                         os.path.join(os.environ.get('HOME'),'.Xauthority'),
                         'DISPLAY': os.environ.get('DISPLAY'),
                         'HOME': os.environ.get('HOME')},
                    SCANNERS=[LaTeX],
                    BUILDERS={'Latify':Latify,
                              'Pdf':Pdf,
                              'Wiki':Wiki,
                              'Build':Build,
                              'Color':Color,
                              'Figs':Figs,
                              'Uses':Uses})
        path = {'darwin': '/sw/bin',
                'irix': '/usr/freeware/bin'}
        for plat in path.keys():
            if sys.platform[:len(plat)] == plat and os.path.isdir(path[plat]):
                self['ENV']['PATH'] = self['ENV']['PATH'] + ':' + path[plat]
        cwd = os.getcwd()
        # create a hierarcical structure
        self.tree = (
            os.path.basename(os.path.dirname(os.path.dirname(cwd))),
            os.path.basename(os.path.dirname(cwd)),
            os.path.basename(cwd))
	self.doc = os.environ.get(
             'RSFDOC',
             os.path.join(os.environ.get('RSFROOT'),'doc'))
        for level in self.tree:
            if level:
                self.doc = os.path.join(self.doc,level)
        mkdir(self.doc)
        if pdfread:
            self.Append(BUILDERS={'Read':Read,'Print':Print})
        if epstopdf:
            self.Append(BUILDERS={'PDFBuild':PDFBuild})
        if fig2dev:
            self.Append(BUILDERS={'XFig':XFig})
        if latex2html:
            self.Append(BUILDERS={'HTML':HTML})
            if pstoimg:
                self.Append(BUILDERS={'PNGBuild':PNGBuild})
                self.imgs = []
        if (acroread and ps2eps) or pdf2ps:
            self.Append(BUILDERS={'PSBuild':PSBuild})
        if mathematica and epstopdf:
            self.Append(BUILDERS={'Math':Math})
        if matlab and epstopdf:
            self.Append(BUILDERS={'Matlab':Matlab})
        self.scons = []
        self.figs = []
        self.uses = []
        self.Dir()
    def Install2(self,dir,fil):
        dir2 = mkdir(dir)
        self.Install(dir2,fil)
    def Dir(self,topdir='.',resdir='Fig'):
        # reproducible directories
        for scons in glob.glob('%s/[a-z]*/SConstruct' % topdir):
            dir = os.path.dirname(scons)
            html = dir+'.html'
            self.Color(html,scons)
            self.scons.append(html)
            uses = dir+'.uses'
            self.Uses(uses,scons,tree=self.tree)
            self.uses.append(uses)

        if self.scons:
            self.Install(self.doc,self.scons)
        self.Alias('figinstall',self.doc)        
        # reproducible figures
        erfigs = []
        eps = {}

        # check figure repository
        vpldir = re.sub(r'.*\/((?:[^\/]+)\/(?:[^\/]+))$',
                        figdir+'/\\1',os.path.abspath(topdir))
        for fig in glob.glob('%s/[a-z]*/*%s' % (vpldir,vpsuffix)):
            eps[fig] = re.sub(r'.*\/([^\/]+)\/([^\/]+)'+vpsuffix+'$',
                              r'%s/\1/%s/\2%s' % (topdir,resdir,pssuffix),fig)
        
        # follow symbolic links
        for pdir in filter(os.path.islink,glob.glob(topdir+'/[a-z]*')):
            vpldir = re.sub(r'.*\/((?:[^\/]+)\/(?:[^\/]+)\/(?:[^\/]+))$',
                            figdir+'/\\1',
                            os.path.abspath(os.path.realpath(pdir)))
            for fig in glob.glob('%s/*%s' % (vpldir,vpsuffix)):
                eps[fig] = re.sub(r'.*\/([^\/]+)\/([^\/]+)'+vpsuffix+'$',
                                  r'%s/%s/\2%s' % (pdir,resdir,pssuffix),fig)
                      
        for fig in eps.keys():
            ps = eps[fig]
            resdir2 = os.path.join(self.doc,os.path.dirname(ps))
            self.Build(ps,fig)
            if epstopdf:
                pdf = re.sub(pssuffix+'$','.pdf',ps)
                self.PDFBuild(pdf,ps)
                erfigs.append(pdf)
            if latex2html and pstoimg:
                png = re.sub(pssuffix+'$','.'+itype,ps)
                self.PNGBuild(png,ps)
                self.imgs.append(png)
                self.Install2(resdir2,[png,pdf])
                self.Alias('figinstall',resdir2)
        self.figs.extend(erfigs)

        # conditionally reproducible figures
        crfigs = []
        # mathematica figures:
        mths = glob.glob('%s/Math/*.ma' % topdir)
        if mths:
            for mth in mths:
                pdf = re.sub(r'([^/]+)\.ma$',
                             os.path.join(resdir,'\g<1>.pdf'),mth)
                if mathematica and epstopdf:
                    self.Math(pdf,mth)
                crfigs.append(pdf)
            mathdir = os.path.join(self.doc,'Math')
            self.Install2(mathdir,mths)
            self.Alias('figinstall',mathdir)
        # matlab figures
        mtls = glob.glob('%s/Matlab/*.ml' % topdir)
        if mtls:
            for mtl in mtls:
                pdf = re.sub(r'([^/]+)\.ml$',
                             os.path.join(resdir,'\g<1>.pdf'),mtl)
                if matlab and epstopdf:
                    self.Matlab(pdf,mtl)
                crfigs.append(pdf)
            matlabdir = os.path.join(self.doc,'Matlab')
            self.Install2(matlabdir,mtls)
            self.Alias('figinstall',matlabdir)
        # xfig figures:
        figs =  glob.glob('%s/XFig/*.fig' % topdir)
        if figs: 
            for fig in figs:
                pdf = re.sub(r'([^/]+)\.fig$',
                             os.path.join(resdir,'\g<1>.pdf'),fig)
                if fig2dev:
                    self.XFig(pdf,fig)
                crfigs.append(pdf)
            resdir2 = os.path.join(self.doc,'XFig')
            self.Install2(resdir2,figs)
            self.Alias('figinstall',resdir2)
        # non-reproducible figures
        nrfigs = crfigs + glob.glob(
            os.path.join(topdir,os.path.join(resdir,'*.pdf'))) 
        for pdf in nrfigs:
             if (acroread and ps2eps) or pdf2ps:
                eps = re.sub('.pdf$',pssuffix,pdf)
                self.PSBuild(eps,pdf)
                if latex2html and pstoimg:
                    png = re.sub(pssuffix+'$','.'+itype,eps)
                    self.PNGBuild(png,eps)
                    self.imgs.append(png)
                    resdir2 = os.path.join(self.doc,os.path.dirname(png))
                    self.Install2(resdir2,[png,pdf])
                    self.Alias('figinstall',resdir2)
        self.figs.extend(nrfigs)
    def Paper(self,paper,lclass='geophysics',scons=1,
              use=None,include=None,options=None,resdir='Fig'):
        ltx = self.Latify(target=paper+'.ltx',source=paper+'.tex',
                          use=use,lclass=lclass,options=options,
                          include=include,resdir=resdir)
        pdf = self.Pdf(target=paper,source=paper+'.ltx')
        self.Figs(target=paper+'.figs',source=paper+'.pdf')
        wiki = self.Wiki(target=paper,source=[ltx,pdf])
        pdf[0].target_scanner = LaTeX
        pdfinstall = self.Install(self.doc,paper+'.pdf')
        self.Alias(paper+'.install',pdfinstall)
        if pdfread:
            self.Alias(paper+'.read',self.Read(paper))
            self.Alias(paper+'.print',self.Print(paper))
        if latex2html and l2hdir:
            hdir = paper+'_html'
            css  = os.path.join(hdir,paper+'.css')
            html = os.path.join(hdir,'index.html')
            icons = os.path.join(hdir,'icons')
            self.InstallAs(css,css0)
            self.Install(icons,glob.glob('%s/*.%s' % (icons0,itype)))
            self.HTML(html,paper+'.ltx')
            self.Depends(self.imgs,pdf)
            self.Depends(html,self.imgs)
            if scons:
                self.Depends(html,self.scons)
            self.Depends(html,pdf)
            self.Depends(html,css)
            self.Depends(html,icons)
            self.Alias(paper+'.html',html)
            docdir = os.path.join(self.doc,hdir)
            dochtml = os.path.join(docdir,'index.html')
            self.Command(dochtml,html,
                         'cd $SOURCE.dir && cp -R * $TARGET.dir && cd ..')
            self.Alias(paper+'.install',dochtml)
            self.Depends(paper+'.install','figinstall')
    def End(self,paper='paper',**kw):
         if os.path.isfile(paper+'.tex'):
            apply(self.Paper,(paper,),kw)
            self.Alias('pdf',paper+'.pdf')
            self.Alias('wiki',paper+'.wiki')
            self.Alias('read',paper+'.read')
            self.Alias('print',paper+'.print')
            self.Alias('html',paper+'.html')
            self.Alias('install',paper+'.install')
            self.Alias('figs',paper+'.figs')
            self.Default('pdf')
         self.Command('dummy.tex',self.figs,Action(dummy))
         if self.uses:
              self.Command('.sf_uses',self.uses,'cat $SOURCES')
         else:
              self.Command('.sf_uses',None,'echo ')

default = TeXPaper()
def Dir(**kw):
     return apply(default.Dir,[],kw)
def Paper(paper,**kw):
    return apply(default.Paper,(paper,),kw)
def Command2(target,source,command):
    return default.Command(target,source,command)
def End(paper='paper',**kw):
    return apply(default.End,(paper,),kw)
def Depends2(target,source):
    return default.Depends(target,source)

if __name__ == "__main__":
     import pydoc
     pydoc.help(TeXPaper)

# 	$Id$
