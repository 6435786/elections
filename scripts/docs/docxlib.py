# -*- coding: utf-8 -*-
"""ספריית Word מימין לשמאל (bidi), בלי תלויות חיצוניות."""
import zipfile
from xml.sax.saxutils import escape
FONT = "Arial"

# ---------- XML ----------
def run(text, bold=False, size=22, color=None):
    rpr = f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/>' + ('<w:b/><w:bCs/>' if bold else '') + (f'<w:color w:val="{color}"/>' if color else '') + f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/><w:rtl/><w:lang w:bidi="he-IL"/>'
    return f'<w:r><w:rPr>{rpr}</w:rPr>' + '<w:br/>'.join(f'<w:t xml:space="preserve">{escape(t)}</w:t>' for t in text.split(chr(10))) + '</w:r>'

def para(text, style=None, bold=False, size=22, color=None, after=120, before=0, jc=None, ind=None, keep=False):
    ppr = (f'<w:pStyle w:val="{style}"/>' if style else '') + ('<w:keepNext/>' if keep else '') + '<w:bidi/>' + f'<w:spacing w:before="{before}" w:after="{after}" w:line="300" w:lineRule="auto"/>' + (f'<w:ind w:start="{ind}"/>' if ind else '') + (f'<w:jc w:val="{jc}"/>' if jc else '')
    return f'<w:p><w:pPr>{ppr}</w:pPr>{run(text, bold, size, color)}</w:p>'

def para_b(btxt, rest):
    ppr = '<w:bidi/><w:spacing w:before="0" w:after="140" w:line="300" w:lineRule="auto"/><w:jc w:val="both"/>'
    return f'<w:p><w:pPr>{ppr}</w:pPr>{run(btxt, True)}{run(rest)}</w:p>'

def table(rows, widths=None):
    n = len(rows[0]); W = 9638; first = 2000 if n > 3 else 1500; rest = (W - first) // (n - 1)
    widths_given = widths is not None
    widths = widths or [first] + [rest] * (n - 1)
    if n == 6 and not widths_given: widths = [2138, 1000, 1000, 1500, 2000, 2000]
    if n == 3 and not widths_given: widths = [2600, 3519, 3519]
    if rows[0][0].startswith("מקומות לפי"): widths = [2738, 1000, 1100, 1600, 1600, 1600]
    bd = '<w:top w:val="single" w:sz="4" w:color="BFBFBF"/><w:bottom w:val="single" w:sz="4" w:color="BFBFBF"/><w:start w:val="single" w:sz="4" w:color="BFBFBF"/><w:end w:val="single" w:sz="4" w:color="BFBFBF"/><w:insideH w:val="single" w:sz="4" w:color="BFBFBF"/><w:insideV w:val="single" w:sz="4" w:color="BFBFBF"/>'
    x = f'<w:tbl><w:tblPr><w:bidiVisual/><w:tblW w:w="{W}" w:type="dxa"/><w:tblBorders>{bd}</w:tblBorders><w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="60" w:type="dxa"/><w:start w:w="90" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/><w:end w:w="90" w:type="dxa"/></w:tblCellMar></w:tblPr>'
    x += '<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths) + '</w:tblGrid>'
    for i, r in enumerate(rows):
        head = i == 0; strong = r[0].startswith("**")
        x += '<w:tr>' + ('<w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>' if head else '<w:trPr><w:cantSplit/></w:trPr>')
        for j, c in enumerate(r):
            c = c.lstrip("*")
            if j >= 1: c = c.replace(" (", chr(10)+"(")
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="E6EFEE"/>' if head else ('<w:shd w:val="clear" w:color="auto" w:fill="F7F6F2"/>' if strong else '')
            x += f'<w:tc><w:tcPr><w:tcW w:w="{widths[j]}" w:type="dxa"/>{shade}<w:vAlign w:val="center"/></w:tcPr>{''.join(para(t, bold=head or strong or j == 0, size=19, after=0) for t in c.split(chr(10)))}</w:tc>'
        x += '</w:tr>'
    return x + '</w:tbl>'


def build(B, OUT):
    body = ''
    for k, d in B:
        if k == "h1": body += para(d, bold=True, size=36, color="2A2722", after=60)
        elif k == "by": body += para(d, size=20, color="6E685E", after=240)
        elif k == "h3": body += para(d, bold=True, size=24, color="2A2722", before=220, after=80, keep=True)
        elif k == "h2": body += para(d, bold=True, size=28, color="136F73", before=280, after=100, keep=True)
        elif k == "p": body += para(d, after=140, jc="both")
        elif k == "pb": body += para_b(d[0], d[1])
        elif k == "note": body += para(d, size=19, color="6E685E", before=80, after=160)
        elif k == "li": body += para("• " + d, after=80, ind=240, jc="both")
        elif k == "table": body += table(d) + para("", after=60)
        elif k == "tablew": body += table(d[0], d[1]) + para("", after=60)
    
    NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    doc = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {NS}><w:body>{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/><w:bidi/></w:sectPr></w:body></w:document>'
    styles = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {NS}><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}" w:eastAsia="{FONT}"/><w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="he-IL" w:bidi="he-IL"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:bidi/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:bidi/></w:pPr><w:rPr><w:rtl/></w:rPr></w:style></w:styles>'
    ct = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    drels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct); z.writestr("_rels/.rels", rels); z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", styles); z.writestr("word/_rels/document.xml.rels", drels)
    print("written", OUT)
