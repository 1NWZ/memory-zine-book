#!/usr/bin/env python3
"""电子回忆书：生成可编辑计划、校验并以原照片渲染PNG。依赖Pillow。"""
import argparse, colorsys, json, math, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

LIB = json.loads((Path(__file__).resolve().parents[1]/'references/layouts.json').read_text())
PALETTE = dict(paper='#F7F6EE',yellow='#F7FC94',green='#087449',plum='#75446F',
               lavender='#B8A1C5',sage='#69766C',blue='#ADE0EF',teal='#00A7A4',
               accent='#E997E8',ink='#242820')

def expected(n, single=False):
    if not 1 <= n <= 9: raise ValueError('仅接受1–9张输入照片')
    return 1 if single or n == 1 else 2 if n <= 3 else 3 if n <= 6 else 4

def read_photo(path):
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert('RGB')

def draft(paths, single=False, cover='R03'):
    n=len(paths); total=expected(n,single)
    photos=[]
    for i,p in enumerate(paths,1):
        im=read_photo(p)
        colors=im.resize((96,96)).quantize(colors=5).convert('RGB').getcolors(96*96)
        photos.append(dict(id=f'U{i:02}',path=str(Path(p).resolve()),size=list(im.size),
            palette=['#%02x%02x%02x'%c for _,c in sorted(colors,reverse=True)],
            focus=[.5,.5],note='待模型视觉分析：主体、关系、裁切安全区'))
    plan=dict(version=1,mode='single' if single else 'book',size=[1600,2133],
        photos=photos,palette=PALETTE.copy(),background={'kind':LIB['covers'][cover]['background']},
        cover_reference=cover,cover_photo='U01',cover_title='日常收藏',pages=[],
        font='',font_italic='',story='待视觉模型根据真实照片补充，不编造日期和关系')
    if single and n>1:
        plan['pages']=[dict(kind='collection',photos=[p['id'] for p in photos],title='日常收藏',footer='每一个小片刻，都值得收藏。')]
    else:
        plan['pages']=[dict(kind='cover')]
        if n>1:
            ids=[p['id'] for p in photos[1:]]; groups=total-1
            chunks=[]; pos=0
            for k in range(groups):
                count=len(ids)//groups+(k<len(ids)%groups)
                chunk=ids[pos:pos+count]; pos+=count
                if len(chunk)==1: chunk=['U01']+chunk
                chunks.append(chunk)
            for k,chunk in enumerate(chunks):
                name='full_double_oval' if len(chunk)==3 else ('full_oval' if k%2==0 else 'diagonal')
                plan['pages'].append(dict(kind='spread',layout=name,photos=chunk,
                    captions=[],reason='初始分组；需根据照片语义、方向和主体位置确认'))
    return plan

def resolve_paths(plan,base):
    for p in plan['photos']:
        p['path']=str((base/p['path']).resolve())
    for key in ('font','font_italic'):
        if plan.get(key): plan[key]=str((base/plan[key]).resolve())
    if plan.get('background',{}).get('path'):
        plan['background']['path']=str((base/plan['background']['path']).resolve())

def spread_ids(page):
    return [s['photo'] for s in page['slots']] if 'slots' in page else page.get('photos',[])

def validate(plan):
    n=len(plan['photos']); count=expected(n,plan.get('mode')=='single')
    if len(plan['pages'])!=count: raise ValueError(f'应为{count}张成图，实际计划{len(plan["pages"])}张')
    ids=[p['id'] for p in plan['photos']]
    if len(set(ids))!=n: raise ValueError('照片ID重复')
    if plan.get('mode')!='single' and plan['pages'][0]['kind']!='cover': raise ValueError('默认书籍必须从封面开始')
    if plan.get('mode')!='single' and sum(p['kind']=='cover' for p in plan['pages'])!=1: raise ValueError('默认必须恰好1张封面')
    if plan['cover_photo'] not in ids: raise ValueError('封面图ID不存在')
    used=[]
    def check_spread(p):
        if p['layout'] not in LIB['spreads']: raise ValueError('未知内页版式')
        seq=spread_ids(p)
        if not seq: raise ValueError('跨页没有照片')
        cap=len(LIB['spreads'][p['layout']]['slots'])
        if 'slots' not in p and len(seq)!=cap: raise ValueError(f'{p["layout"]}需要{cap}个槽位映射，可显式复用真实照片；不得默默丢图')
        if 'slots' in p:
            for s in p['slots']:
                if s.get('page') not in (0,1): raise ValueError('槽位page必须为0或1')
                x,y,w,h=s['box']
                if min(x,y)<0 or min(w,h)<=0 or x+w>1.001 or y+h>1.001: raise ValueError('槽位超出纸页')
        used.extend(seq)
    for p in plan['pages']:
        kind=p['kind']
        if kind=='cover': used.append(plan['cover_photo'])
        elif kind=='spread': check_spread(p)
        elif kind=='stack':
            if len(p['spreads'])!=2: raise ValueError('上下陈列恰好两组跨页')
            for s in p['spreads']: check_spread(s)
        elif kind=='collection': used.extend(p['photos'])
        else: raise ValueError('未知成图类型')
    if set(used)-set(ids): raise ValueError('引用了不存在的用户照片')
    only_cover=plan.get('mode')=='single' and plan['pages'][0]['kind']=='cover'
    if set(ids)-set(used) and not only_cover: raise ValueError('有用户照片未出现在成品中')
    if min(plan['size'])<400 or max(plan['size'])>8000: raise ValueError('尺寸须在400–8000之间')
    for p in plan['photos']:
        if not Path(p['path']).is_file(): raise ValueError(f'照片不存在：{p["path"]}')
        if any(not 0<=v<=1 for v in p.get('focus',[.5,.5])): raise ValueError('focus必须在0–1内')

class Renderer:
    def __init__(self,plan):
        self.p=plan; self.palette={**PALETTE,**plan.get('palette',{})}
        self.photos={p['id']:p for p in plan['photos']}; self.cache={}; self.warnings=[]
        self.font_path=self.find_font(plan.get('font'))
        self.italic=plan.get('font_italic') or self.font_path
    def find_font(self,path):
        if path:
            ImageFont.truetype(path,20); return path
        candidates=['/System/Library/Fonts/PingFang.ttc','/System/Library/Fonts/STHeiti Light.ttc',
          '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
          'C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
        for p in candidates:
            if Path(p).exists(): return p
        raise ValueError('未找到字体，请在计划font字段提供支持中文的字体路径')
    def color(self,c): return self.palette.get(c,c)
    def text(self,im,xy,s,size=18,fill='ink',anchor='la',italic=False):
        if not s: return
        f=ImageFont.truetype(self.italic if italic else self.font_path,max(8,int(size)))
        ImageDraw.Draw(im).text(xy,s,font=f,fill=self.color(fill),anchor=anchor)
    def texture(self,size,color,seed=8):
        im=Image.new('RGB',size,self.color(color)); rng=random.Random(seed)
        # 低振幅、可复现纸面颗粒；不将噪点叠到用户照片上。
        noise=Image.new('L',(max(1,size[0]//2),max(1,size[1]//2)))
        noise.putdata([rng.randrange(110,146) for _ in range(noise.width*noise.height)])
        noise=noise.resize(size)
        return Image.blend(im,Image.merge('RGB',(noise,noise,noise)),.025)
    def background(self,size):
        cfg=self.p.get('background',{}); kind=cfg.get('kind','dots')
        if cfg.get('path'): return ImageOps.fit(read_photo(cfg['path']),size)
        colors={'dots':'#DADBD7','paper':'#DDDBD7','fiber':'#537659','dark':'#343739','navy':'#19354C','gingham':'#F3F7F6','black':'#050505'}
        im=self.texture(size,colors.get(kind,'#DEDFD8')); d=ImageDraw.Draw(im); w,h=size
        if kind in ('dots','navy'):
            step=max(20,int(w*.16)); r=max(2,int(w*(.009 if kind=='dots' else .0035)))
            for row,y in enumerate(range(int(step*.3),h,step)):
                for x in range(int(step*.3)+row%2*(step//2),w,step):
                    d.ellipse((x-r,y-r,x+r,y+r),fill='#F3F4EF' if kind=='dots' else '#BAB597')
        elif kind=='gingham':
            layer=Image.new('RGBA',size); ld=ImageDraw.Draw(layer); step=max(24,w//15)
            for x in range(0,w,step*2): ld.rectangle((x,0,x+step,h),fill=(165,204,229,65))
            for y in range(0,h,step*2): ld.rectangle((0,y,w,y+step),fill=(165,204,229,65))
            im=Image.alpha_composite(im.convert('RGBA'),layer).convert('RGB')
        elif kind in ('fiber','dark'):
            self.warnings.append('fiber/dark代码底纹仅为简化替代；追求参考摄影材质时提供AI生成background.path')
            if kind=='fiber':
                rng=random.Random(19)
                for _ in range(w*2):
                    x=rng.randrange(-w,w*2); y=rng.randrange(h)
                    d.line((x,y,x+w*.4,y-w*.12),fill=rng.choice(['#597D60','#53765A','#628366']),width=1)
            else:
                glow=Image.new('RGB',size,'#282B2D'); gd=ImageDraw.Draw(glow)
                gd.rectangle((w*.17,h*.17,w*.44,h*.64),fill='#B7ACBF')
                gd.rectangle((w*.50,h*.17,w*.68,h*.64),fill='#A59CAE')
                im=Image.blend(im,glow.filter(ImageFilter.GaussianBlur(w*.025)),.7)
        return im
    def paste_photo(self,im,uid,box,shape='rect',style='line',focus=None,crop=None):
        x,y,w,h=map(round,box); w=max(1,w); h=max(1,h)
        if uid not in self.cache: self.cache[uid]=read_photo(self.photos[uid]['path'])
        source=self.cache[uid]
        if crop:
            a,b,c,d=crop
            if not (0<=a<c<=1 and 0<=b<d<=1): raise ValueError('crop须为有效的归一化[x0,y0,x1,y1]')
            source=source.crop((round(a*source.width),round(b*source.height),round(c*source.width),round(d*source.height)))
        if w>source.width*1.8 or h>source.height*1.8: self.warnings.append(f'{uid}在大图槽位可能清晰度不足')
        fitted=ImageOps.fit(source,(w,h),method=Image.Resampling.LANCZOS,centering=tuple(focus or self.photos[uid].get('focus',[.5,.5])))
        mask=None
        if shape=='ellipse':
            mask=Image.new('L',(w,h)); ImageDraw.Draw(mask).ellipse((0,0,w-1,h-1),fill=255)
        im.paste(fitted,(x,y),mask)
        if style in ('line','accent'):
            d=ImageDraw.Draw(im); stroke=max(1,round(im.width*(.005 if style=='accent' else .0009)))
            fn=d.ellipse if shape=='ellipse' else d.rectangle
            fn((x,y,x+w-1,y+h-1),outline=self.color('accent' if style=='accent' else 'ink'),width=stroke)
    def mount(self,bg,book,box,cover=False):
        x,y,w,h=map(round,box); book=book.resize((w,h),Image.Resampling.LANCZOS).convert('RGBA')
        mask=Image.new('L',(w,h)); md=ImageDraw.Draw(mask)
        if cover:
            md.rounded_rectangle((0,0,w-1,h-1),radius=max(2,w//70),fill=255)
            md.rectangle((0,0,w//2,h-1),fill=255)
        else: md.rectangle((0,0,w-1,h-1),fill=255)
        shadow=Image.new('RGBA',bg.size); sh=Image.new('RGBA',(w,h),(0,0,0,65)); sh.putalpha(mask.point(lambda v:int(v*.23)))
        shadow.paste(sh,(x+int(w*.008),y+int(w*.016)))
        result=Image.alpha_composite(bg.convert('RGBA'),shadow.filter(ImageFilter.GaussianBlur(max(2,w*.018))))
        result.paste(book,(x,y),mask)
        return result.convert('RGB')
    def cover(self,size):
        ref=LIB['covers'][self.p['cover_reference']]; W,H=size
        x,y,w,h=[round(v*(W if i%2==0 else H)) for i,v in enumerate(ref['book'])]
        book=self.texture((w,h),self.p.get('cover_color',ref['color']))
        d=ImageDraw.Draw(book)
        for i in range(max(2,int(w*.045))):
            v=int(32*math.exp(-((i-w*.025)/(w*.01))**2))
            # 窄书脊阴影，不做宽灰色条。
            d.line((i,0,i,h),fill=tuple(max(0,c-v) for c in book.getpixel((min(w-1,i+40),0))))
        box=[v*(w if i%2==0 else h) for i,v in enumerate(ref['window'])]
        self.paste_photo(book,self.p['cover_photo'],box,style='none')
        self.text(book,(w*.5,h*.929),self.p.get('cover_title','日常收藏'),w*.022,anchor='mm')
        d=ImageDraw.Draw(book); d.line((0,h-2,w,h-2),fill='#B9BAA1',width=max(1,h//600))
        return self.mount(self.background(size),book,(x,y,w,h),True)
    def decorations(self,im,name,pw,ph,stage):
        typ,page=name.split(':'); page=int(page); ox=page*pw; d=ImageDraw.Draw(im)
        if typ=='dots' and stage=='before':
            step=max(15,int(pw*.08)); r=max(1,int(pw*.004))
            for row,y in enumerate(range(step//2,ph,step)):
                for x in range(step//2+(row%2)*step//2,pw,step):
                    d.ellipse((ox+x-r,y-r,ox+x+r,y+r),fill='#E4E4E1')
        if stage!='after': return
        if typ=='squares':
            for x,y,c in [(.16,.11,'#FFF02D'),(.77,.07,'#E990EF'),(.33,.185,'#A9F3DF'),(.87,.69,'#19A269'),(.10,.78,'#FFF02D'),(.69,.88,'#EC1423')]:
                a=pw*.04; d.rectangle((ox+x*pw,y*ph,ox+x*pw+a,y*ph+a),fill=c)
        elif typ=='orbit':
            for i,(x,y) in enumerate([(.17,.085),(.34,.17),(.80,.18),(.86,.36),(.25,.80),(.82,.87)],1):
                cx=ox+x*pw; cy=y*ph; r=pw*.020
                d.ellipse((cx-r,cy-r,cx+r,cy+r),fill='#FAFAF6',outline='#33352D',width=max(1,pw//650))
                self.text(im,(cx,cy),str(i),pw*.022,anchor='mm')
        elif typ=='ab':
            for t,y in [('a.',.10),('b.',.62)]:
                x=ox+pw*.16; yy=ph*y
                d.rectangle((x,yy,x+pw*.043,yy+pw*.043),fill='#F6FA71')
                self.text(im,(x,yy),t,pw*.032)
            self.text(im,(ox+pw*.5,ph*.51),'每一天，都值得收藏',pw*.026,anchor='mm')
            for k in range(3):
                cx=ox+pw*(.80+k*.011); cy=ph*(.505-k*.012); rr=pw*(.005+k*.003)
                d.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),outline='#282923',width=1)
        elif typ=='stars':
            for cx,cy,r in [(.80,.07,.03),(.91,.03,.036),(.87,.19,.025),(.72,.17,.025),(.84,.28,.035)]:
                pts=[]
                for i in range(10):
                    a=-math.pi/2+i*math.pi/5; rr=pw*r*(1 if i%2==0 else .44)
                    pts.append((ox+cx*pw+math.cos(a)*rr,cy*ph+math.sin(a)*rr))
                d.polygon(pts,fill='#BFC1BA')
    def spread(self,page,width=1440):
        pw=width//2; ph=round(pw*math.sqrt(2)); spec=LIB['spreads'][page['layout']]
        colors=page.get('colors',spec['colors']); im=Image.new('RGB',(pw*2,ph))
        for i,c in enumerate(colors): im.paste(self.texture((pw,ph),c),(i*pw,0))
        deco=page.get('decor',spec['decor'])
        for name in deco: self.decorations(im,name,pw,ph,'before')
        if 'slots' in page: slots=page['slots']
        else: slots=[dict(s,photo=uid) for s,uid in zip(spec['slots'],page['photos'])]
        for k,s in enumerate(slots,1):
            b=s['box']; x=s['page']*pw+b[0]*pw; y=b[1]*ph; w=b[2]*pw; h=b[3]*ph
            style=s.get('style','line')
            if style=='polaroid':
                ImageDraw.Draw(im).rectangle((x,y,x+w,y+h),fill='#F1F1E9')
                m=w*.065
                self.paste_photo(im,s['photo'],(x+m,y+m,w-2*m,h-w*.25),focus=s.get('focus'),crop=s.get('crop'))
            elif style=='split':
                # 同一完整场景顺序切片，保留内容连续性。
                tmp=Image.new('RGB',(round(w),round(h)))
                self.paste_photo(tmp,s['photo'],(0,0,w,h),style='none',focus=s.get('focus'),crop=s.get('crop'))
                gap=round(pw*.03); cut=round(w*.43)
                im.paste(tmp.crop((0,0,cut-gap//2,tmp.height)),(round(x),round(y)))
                im.paste(tmp.crop((cut+gap//2,0,tmp.width,tmp.height)),(round(x)+cut+gap//2,round(y)))
            else:
                self.paste_photo(im,s['photo'],(x,y,w,h),s.get('shape','rect'),style,s.get('focus'),s.get('crop'))
            if page.get('numbers',False) and style!='none':
                self.text(im,(x,y+h+ph*.013),f'({k:02})',pw*.018)
        for name in deco: self.decorations(im,name,pw,ph,'after')
        if page.get('dotted_rings'):
            d=ImageDraw.Draw(im)
            for page_no,cx,cy,c in [(0,.02,.43,colors[1]),(1,.94,.55,colors[0])]:
                # 各半页独立绘制及裁切，不让点环串到另一页。
                layer=Image.new('RGBA',(pw,ph)); ld=ImageDraw.Draw(layer)
                for j in range(18):
                    a=j*2*math.pi/18; x=pw*(cx+.13*math.cos(a)); y=ph*cy+pw*.13*math.sin(a); r=pw*.008
                    ld.ellipse((x-r,y-r,x+r,y+r),fill=self.color(c))
                im.paste(layer,(page_no*pw,0),layer)
        for cap in page.get('captions',[]):
            ox=cap.get('page',0)*pw; x,y=cap['at']
            self.text(im,(ox+x*pw,y*ph),cap['text'],pw*cap.get('size',.026),cap.get('color','ink'),cap.get('anchor','la'),cap.get('italic',False))
        # 页缝压痕采用窄渐变，不让暗线扩大成第三列。
        d=ImageDraw.Draw(im)
        for off,color in [(-2,'#B8B9AE'),(-1,'#828A7F'),(0,'#5F695F'),(1,'#C6CABD'),(2,'#EBEBDD')]: d.line((pw+off,0,pw+off,ph),fill=color)
        return im
    def collection(self,page,size):
        W,H=size; im=self.texture(size,page.get('color','yellow')); ids=page['photos']; cols=min(3,len(ids))
        self.text(im,(W*.043,H*.112),page.get('title','日常收藏'),W*.021)
        for i,uid in enumerate(ids):
            row=i//3; col=i%3; row_n=min(3,len(ids)-row*3)
            x=(.043+(3-row_n)*.154+col*.308)*W; y=(.148+row*.2085)*H
            self.paste_photo(im,uid,(x,y,W*.299,H*.137))
            self.text(im,(x+W*.1495,y+H*.151),f'({i+1})',W*.020,anchor='mm')
        self.text(im,(W*.94,H*.936),page.get('footer','每一个小片刻，都值得收藏。'),W*.019,anchor='ra')
        return im
    def render_page(self,page,size):
        W,H=size
        if page['kind']=='cover': return self.cover(size)
        if page['kind']=='collection': return self.collection(page,size)
        bg=self.background(size)
        if page['kind']=='stack':
            for idx,s in enumerate(page['spreads']):
                book=self.spread(s,max(800,round(W*.747)))
                w=W*.747; h=w/math.sqrt(2); y=H*(.075 if idx==0 else .529)
                bg=self.mount(bg,book,(W*.127,y,w,h))
            return bg
        book=self.spread(page,max(1200,round(W*.927)))
        if page.get('view_crop'):
            x0,y0,x1,y1=page['view_crop']
            if not(0<=x0<x1<=1 and 0<=y0<y1<=1): raise ValueError('view_crop范围错误')
            book=book.crop((int(x0*book.width),int(y0*book.height),int(x1*book.width),int(y1*book.height)))
        # 局部特写可自设mount；正常跨页保持√2宽高比。
        if page.get('mount'):
            b=page['mount']; x,y,w,h=[b[i]*(W if i%2==0 else H) for i in range(4)]
            if abs((w/h)/(book.width/book.height)-1)>.03: raise ValueError('mount会拉伸书本，请按裁后宽高比计算')
        else:
            w=W*.927; h=w*book.height/book.width; x=(W-w)/2; y=(H-h)/2
        return self.mount(bg,book,(x,y,w,h))

def main():
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('plan'); p.add_argument('photos',nargs='+'); p.add_argument('--out',required=True); p.add_argument('--single',action='store_true'); p.add_argument('--cover',choices=list(LIB['covers']),default='R03')
    p=sub.add_parser('render'); p.add_argument('plan'); p.add_argument('--out',required=True)
    p=sub.add_parser('validate'); p.add_argument('plan')
    args=parser.parse_args()
    if args.cmd=='plan':
        plan=draft(args.photos,args.single,args.cover); target=Path(args.out)
        if target.exists(): raise ValueError('计划文件已存在，请选择新路径或明确编辑已有计划')
        target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps(plan,ensure_ascii=False,indent=2)); print(target); return
    path=Path(args.plan).resolve(); plan=json.loads(path.read_text()); resolve_paths(plan,path.parent); validate(plan)
    if args.cmd=='validate': print('数量、槽位引用、输入覆盖和文件路径校验通过'); return
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()): raise ValueError('输出目录须为空，避免混入旧图或覆写成品')
    renderer=Renderer(plan); files=[]
    for i,page in enumerate(plan['pages']):
        filename=f'{i:02}_{page["kind"]}.png'; renderer.render_page(page,tuple(plan['size'])).save(out/filename)
        files.append(filename)
    report=dict(files=files,count=len(files),warnings=sorted(set(renderer.warnings)),
                checks='程序仅检查可计算约束；人物保真、裁切安全和中文字形必须逐图视觉检查。')
    # 报告写在输出目录外，目录内只保留规定数量的成品PNG。
    (out.parent/(out.name+'-report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
