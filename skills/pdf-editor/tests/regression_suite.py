#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / 'scripts' / 'pdf_editor.py'


def run(*args, expect_ok=True, env=None):
    p = subprocess.run([sys.executable, str(EDITOR), *map(str,args)], capture_output=True, text=True, env=env)
    try:
        data = json.loads(p.stdout)
    except Exception as exc:
        raise AssertionError(f'non-json stdout: {p.stdout!r} stderr={p.stderr!r}') from exc
    if expect_ok:
        assert p.returncode == 0 and data.get('ok') is True, (p.returncode, data, p.stderr)
    else:
        assert p.returncode != 0 and data.get('ok') is False, (p.returncode, data, p.stderr)
    return data, p.stderr


def save_plan(path: Path, ops):
    path.write_text(json.dumps({'operations': ops}, ensure_ascii=False), encoding='utf-8')


def make_sample(path: Path):
    d = fitz.open()
    p = d.new_page(width=595, height=842)
    p.insert_text((72,100), '客户地址：乌审旗刘总', fontsize=14, fontname='china-s')
    p.insert_text((72,140), 'Order ABC-123', fontsize=12, fontname='helv')
    p2 = d.new_page(width=595, height=842)
    p2.insert_text((72,100), '第二页 乌审旗 测试 乌审旗', fontsize=14, fontname='china-s')
    d.save(path); d.close()


def make_png(path: Path, rgb):
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0,0,80,30), False)
    pix.clear_with((rgb[0] << 16) | (rgb[1] << 8) | rgb[2])
    pix.save(path)


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix='pdf-editor-regression-') as td:
        td = Path(td)
        src = td/'sample.pdf'; make_sample(src)
        logo1 = td/'logo1.png'; logo2 = td/'logo2.png'
        make_png(logo1, (220,220,220)); make_png(logo2, (100,100,100))

        info,_ = run('info','--input',src)
        assert info['classification']['primary_type'] == 'native'
        results.append(('pdf_classification','PASS'))

        plan=td/'replace.json'; out=td/'replace.pdf'
        save_plan(plan,[{'action':'replace_text','pages':'all','old':'乌审旗','new':'杭锦旗','font_policy':'auto'}])
        r,events=run('apply','--input',src,'--output',out,'--plan',plan, env={**__import__('os').environ,'PDF_EDITOR_PROGRESS':'1'})
        assert r['validation']['semantic_ok'] and r['validation']['visual_ok']
        assert r['validation']['visual']['glyph_validation']
        assert all(p['non_target_diff'] <= 0.003 for p in r['validation']['visual']['pages'])
        assert 'tool.progress' in events and 'file.ready' in events
        results.append(('v2_equal_length_text_replace_preserved','PASS'))
        results.append(('post_save_visual_regression','PASS'))
        results.append(('jsonl_progress_events','PASS'))

        plan=td/'occ.json'; out=td/'occ.pdf'
        save_plan(plan,[{'action':'replace_text','pages':[2],'old':'乌审旗','new':'杭锦旗','occurrence':1}])
        r,_=run('apply','--input',src,'--output',out,'--plan',plan)
        sem=r['semantic_validation'][0]
        assert sem['old_remaining']==1 and sem['new_count']==1 and sem['ok']
        results.append(('scoped_nth_occurrence','PASS'))

        plan=td/'ops.json'; out=td/'ops.pdf'
        save_plan(plan,[
            {'action':'delete_text','pages':[1],'text':'Order ABC-123'},
            {'action':'insert_pages','at':2,'count':1,'copy_size_from':1},
            {'action':'reorder_pages','order':[3,1,2]},
            {'action':'add_image','pages':[1],'path':str(logo1),'rect':[420,60,540,105]},
            {'action':'replace_image','page':1,'image_index':1,'path':str(logo2)},
            {'action':'add_text','pages':[2],'text':'Added','position':'bottom-left','font_size':10},
            {'action':'watermark','pages':[3],'text':'QA','font_size':24,'opacity':0.1},
            {'action':'page_numbers','pages':'all','format':'{page}/{total}','font_size':9},
        ])
        r,_=run('apply','--input',src,'--output',out,'--plan',plan)
        assert r['validation']['pages']==3
        results.append(('delete_insert_reorder_add_replace_image_watermark_pagenum','PASS'))

        extract=td/'extract.pdf'; r,_=run('extract','--input',out,'--output',extract,'--pages','1,3')
        assert r['validation']['pages']==2
        results.append(('extract_pages','PASS'))

        merge=td/'merge.pdf'; r,_=run('merge','--output',merge,extract,extract)
        assert r['validation']['pages']==4
        results.append(('merge','PASS'))

        splitdir=td/'split'; r,_=run('split','--input',merge,'--output-dir',splitdir,'--chunk-size','2')
        assert len(r['outputs'])==2 and all(x['validation']['pages']==2 for x in r['outputs'])
        results.append(('split','PASS'))

        bad_plan=td/'bad.json'; save_plan(bad_plan,[{'action':'delete_pages','pages':[1,2]}])
        run('apply','--input',src,'--output',td/'bad.pdf','--plan',bad_plan, expect_ok=False)
        results.append(('refuse_delete_all_pages','PASS'))

        run('extract','--input',src,'--output',src,'--pages','1', expect_ok=False)
        results.append(('refuse_source_overwrite','PASS'))

    print(json.dumps({'ok':True,'tests':[{'name':n,'status':s} for n,s in results]}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
