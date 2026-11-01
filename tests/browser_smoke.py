"""Optional: pip install playwright; playwright install chromium.
Start uvicorn, then run this script. Tests interaction, not physical accuracy.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
photo=root.parent/'uploads/20260923_204146.jpg'
if not photo.exists():
    # Portable fallback for downloaded project.
    from PIL import Image, ImageDraw
    photo=root/'tests/browser-sample.png'
    im=Image.new('RGB',(800,1100),'#303030');d=ImageDraw.Draw(im)
    d.rectangle((100,100,700,1000),fill='white',outline='black',width=4)
    im.save(photo)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8085/',wait_until='networkidle')
    assert page.locator('#verifyBtn').count()==1
    page.locator('#fileInput').set_input_files(str(photo))
    page.wait_for_function('window.app && window.app.image && !window.app.processBtn.disabled',timeout=60000)
    source=page.evaluate('({w:app.imageWidth,h:app.imageHeight})')
    page.set_viewport_size({'width':1280,'height':720})
    page.wait_for_timeout(80)

    # Mode rows should scroll inside the left panel, without moving/resizing the
    # fixed desktop workspace or adding page-level scrolling.
    layout_before=page.evaluate('''()=>({canvas:(()=>{const r=app.canvas.getBoundingClientRect();return [r.width,r.height]})(),
      zoom:app.scale,docScroll:document.documentElement.scrollHeight,view:innerHeight})''')

    # Check that CSS does not distort the source image aspect ratio.
    def choose_mode(value):
        page.locator(f'input[name="refMode"][value="{value}"]').evaluate(
            '(e)=>{e.checked=true;e.dispatchEvent(new Event("change",{bubbles:true}))}')
        page.wait_for_function('''()=>Math.abs(app.canvas.height-app.canvas.getBoundingClientRect().height)<1 &&
          Math.abs(app.canvas.width-app.canvas.getBoundingClientRect().width)<1''')
        ratio=page.evaluate('''()=>{const c=app.canvas,r=c.getBoundingClientRect();
          return (app.imageWidth*app.scale*r.width/c.width)/(app.imageHeight*app.scale*r.height/c.height)}''')
        assert abs(ratio-source['w']/source['h'])<0.002, (value,ratio)

    # Regression: ruler/custom controls alter layout height; the preview should
    # remain undistorted, and R1/R2 must be clickable at their rendered positions.
    choose_mode('ruler')
    for i in (0, 1):
        before=page.evaluate('i=>app.rulerPoints[i].slice()', i)
        xy=page.evaluate('''i=>{const c=app.canvas,r=c.getBoundingClientRect(),p=app.imgToScreen(...app.rulerPoints[i]);
          return [r.left+p.x*r.width/c.width,r.top+p.y*r.height/c.height]}''', i)
        page.mouse.move(*xy)
        page.mouse.down()
        assert page.evaluate('app.activeRulerIndex')==i, f'R{i+1} was not selected'
        page.mouse.move(xy[0]+24,xy[1]+16,steps=3)
        moved=page.evaluate('i=>app.rulerPoints[i].slice()', i)
        assert moved!=before, f'R{i+1} did not move'
        page.mouse.up()
    choose_mode('custom')
    layout_after=page.evaluate('''()=>{const p=document.querySelector('.control-panel'),r=app.canvas.getBoundingClientRect();
      const pageY=scrollY,old=p.scrollTop;p.scrollTop=old+160;
      return {canvas:[r.width,r.height],zoom:app.scale,panelScrolls:p.scrollHeight>p.clientHeight,
        panelMoved:p.scrollTop>old,pageY:scrollY,docScroll:document.documentElement.scrollHeight,view:innerHeight}}''')
    assert layout_after['panelScrolls'] and layout_after['panelMoved'], layout_after
    assert layout_after['pageY']==0 and layout_after['docScroll']<=layout_after['view']+1, layout_after
    assert max(abs(a-b) for a,b in zip(layout_before['canvas'],layout_after['canvas']))<1, (layout_before,layout_after)
    assert abs(layout_before['zoom']-layout_after['zoom'])<1e-12, (layout_before,layout_after)
    choose_mode('a4_portrait')
    # Restore the standard viewport for downstream measurement-interaction checks.
    page.set_viewport_size({'width':1440,'height':1000})
    page.wait_for_timeout(80)
    page.locator('#autoCornersBtn').click()
    page.wait_for_function('document.querySelector("#toolbarStatus").textContent.includes("Corner suggestions") || document.querySelector("#toolbarStatus").textContent.includes("No reference found")')
    page.locator('#processBtn').click()
    page.wait_for_function('window.app.lastResult',timeout=60000)
    result=page.evaluate('app.lastResult')
    assert result['metadata']['width_px']==2100
    assert result['metadata']['height_px']==2970
    for url in result['download'].values():
        response=page.request.get('http://127.0.0.1:8085'+url)
        assert response.status==200
    page.locator('#verifyBtn').click()
    page.wait_for_function('app.measureTool.image && app.measureTool.canvas.width>0')
    def point(x,y):
        return page.evaluate('''([x,y])=>{const t=app.measureTool,r=t.canvas.getBoundingClientRect();
          return [r.left+t.panX+x*t.scale,r.top+t.panY+y*t.scale];}''',[x,y])
    page.mouse.click(*point(200,400)); page.mouse.click(*point(200,1400))
    m=page.evaluate('app.measureTool.measurement()')
    assert abs(m['measured_mm']-100)<.3,m
    with page.expect_download() as dl:
        page.locator('#measureSave').click()
    downloaded=json.loads(Path(dl.value.path()).read_text())
    assert len(downloaded['checks'])==1
    page.screenshot(path=str(root/'analysis/browser-measurement.png'))
    page.keyboard.press('Escape')
    assert page.locator('#measureDialog').is_hidden()
    # UI-scale error must not change image-coordinate distance under zoom.
    page.locator('#verifyBtn').click()
    page.mouse.move(*point(200,800)); page.mouse.wheel(0,-120)
    page.wait_for_function('app.measureTool.scale > 0')
    after=page.evaluate('app.measureTool.measurement()')
    assert abs(m['measured_mm']-after['measured_mm'])<1e-8
    page.locator('#measureReset').click()
    assert page.locator('#measureSave').is_disabled()
    page.locator('#measureClose').click()
    page.locator('#closeOutputBtn').click()
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_timeout(80)
    page.screenshot(path=str(root/'analysis/browser-mobile.png'),full_page=True)
    mobile_view=page.evaluate('''()=>({widthOk:document.documentElement.scrollWidth<=innerWidth,
      imageBounds:[app.panX,app.panY,app.panX+app.imageWidth*app.scale,app.panY+app.imageHeight*app.scale],
      canvas:[app.canvas.width,app.canvas.height]})''')
    assert mobile_view['widthOk'], mobile_view
    assert mobile_view['imageBounds'][0]>=-1 and mobile_view['imageBounds'][1]>=-1, mobile_view
    assert mobile_view['imageBounds'][2]<=mobile_view['canvas'][0]+1 and mobile_view['imageBounds'][3]<=mobile_view['canvas'][1]+1, mobile_view
    assert not errors, errors
    browser.close()
    print(json.dumps({'status':'PASS','source':source,'output':[2100,2970],
                      'checks':['upload','EXIF display','independent sidebar scroll/no desktop page overflow',
                                'ruler/custom mode switches preserve preview aspect ratio',
                                'R1/R2 selection and drag under CSS/backing-store scaling',
                                'redetect','A4 process','4 downloads','measurement clicks','100mm numeric distance','JSON export',
                                'zoom invariance','reset','dialog close','mobile overflow'],
                      'browser_errors':errors},indent=2))
