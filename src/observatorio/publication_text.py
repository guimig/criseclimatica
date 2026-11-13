"""Extract only the article body; menus and unrelated headlines are excluded."""
from html.parser import HTMLParser
import re


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth=0;self.hidden=0;self.parts=[];self.finished=False

    def handle_starttag(self,tag,attrs):
        if self.finished:return
        if not self.depth:
            classes=dict(attrs).get('class','').split()
            if 'entry-content' not in classes:return
            self.depth=1;return
        if tag not in ('br','hr','img','input','meta','link','source','wbr'):self.depth+=1
        if tag in ('script','style'):self.hidden+=1
        if tag in ('p','div','h2','h3','h4','li','br'):self.parts.append('\n')

    def handle_endtag(self,tag):
        if not self.depth or self.finished:return
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
        if tag not in ('br','hr','img','input','meta','link','source','wbr'):self.depth-=1
        if tag in ('p','div','h2','h3','h4','li'):self.parts.append('\n')
        if self.depth==0:self.finished=True

    def handle_data(self,data):
        if self.depth and not self.hidden and not self.finished:self.parts.append(data)


def extract(raw):
    parser=ArticleText()
    parser.feed(raw.decode('utf-8'))
    text=re.sub(r'[ \t]+',' ',''.join(parser.parts))
    return re.sub(r'\n\s*\n+','\n',text).strip()[:12000]
