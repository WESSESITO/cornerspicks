#!/usr/bin/env python3
"""Aplica data/fondos.json a las páginas: capas de fondo, pie de fotos y créditos en metodologia.html."""
import json, re, html, os
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
F = json.load(open('data/fondos.json', encoding='utf-8'))
E = lambda s: html.escape(s or '', quote=True)
PN = {'index': 'Inicio', 'picks-del-dia': 'Picks del día', 'bot-10-minutos': '10 Minutos', 'picksters-over-corners': 'Over Córners',
      'cornes-en-vivo': 'En Vivo', 'en-juego': 'En juego', 'metodologia': 'Metodología', 'comunidad': 'Comentarios'}
pages = {}
for f in F:
    pages.setdefault(f['pagina'], []).append(f)
for page, fs in pages.items():
    fn = page + '.html'
    s = open(fn, encoding='utf-8').read()
    s = re.sub(r'<div class="bgfx".*?</div></div>\n?', '', s, flags=re.S)
    s = re.sub(r'<div class="fotocred">.*?</div>', '', s, flags=re.S)
    def st(f, i):
        v = (f"--pos:{f['pos']};" if f.get('pos') else '') + (f"--posm:{f['pos_movil']};" if f.get('pos_movil') else '')
        if i == 0:
            v += f"background-image:url('{f['archivo']}')"
        return (f' style="{v}"' if v else '') + ('' if i == 0 else f' data-src="{f["archivo"]}"')
    layers = ''.join(f'<div class="bgl{" on" if i == 0 else ""}"{st(f, i)}></div>' for i, f in enumerate(fs))
    s = s.replace('<header class="top">', f'<div class="bgfx" aria-hidden="true">{layers}</div>\n<header class="top">', 1)
    cred = 'Fotos de fondo: ' + ' y '.join(f'{E(f["jugador"])} ({E(f["evento"])})' for f in fs) + \
           ' · <a href="metodologia.html#creditos">créditos de las imágenes</a>'
    s = s.replace('</div></footer>', f'<div class="fotocred">{cred}</div></div></footer>', 1)
    open(fn, 'w', encoding='utf-8').write(s)
rows = ''
for f in F:
    lic = (f'<a href="{E(f["licencia_url"])}" rel="license noopener" target="_blank">{E(f["licencia_detalle"])}</a>'
           if f['licencia_url'] else E(f['licencia_detalle']))
    rows += (f'<tr><td>{PN[f["pagina"]]}</td><td><b>{E(f["jugador"])}</b><br><span class="muted small">{E(f["evento"])}</span></td>'
             f'<td><a href="{E(f["commons"])}" target="_blank" rel="noopener">{E(f["titulo"])}</a></td>'
             f'<td>{E(f["autor"])}<br><span class="muted small">{E(f["fuente"][:90])}</span></td><td>{E(f["fecha"])}</td><td>{lic}</td></tr>')
sa = [f for f in F if 'BY-SA' in f['licencia']]
sa_txt = ' '.join(f'La foto de {E(f["jugador"])} tiene licencia {E(f["licencia"])}: nuestra versión modificada se comparte con esa misma licencia.' for f in sa)
rec_txt = ' '.join(f'La foto de {E(f["jugador"])} además está {E(f["modificacion"])}.' for f in F if f.get('modificacion'))
sec = f'''<h2 id="creditos">Créditos de las imágenes</h2>
<div class="card"><p>Las fotos de fondo son imágenes históricas de <a href="https://commons.wikimedia.org/" target="_blank" rel="noopener">Wikimedia Commons</a> en dominio público o con licencia libre (CC0, CC BY-SA). <b>Modificaciones:</b> todas se muestran en escala de grises, con contraste ajustado, tamaño reducido, un tinte verde y mucha transparencia. {sa_txt} {rec_txt}</p>
<div class="tablewrap"><table class="cred"><thead><tr><th>Página</th><th>Foto</th><th>Archivo en Commons</th><th>Autor / fuente</th><th>Fecha</th><th>Licencia</th></tr></thead><tbody>{rows}</tbody></table></div></div><!--/creditos-->
'''
m = open('metodologia.html', encoding='utf-8').read()
m = re.sub(r'<h2 id="creditos">.*?<!--/creditos-->\n?', '', m, flags=re.S)
m = m.replace('<div class="rg">', sec + '<div class="rg">', 1)
open('metodologia.html', 'w', encoding='utf-8').write(m)
usados = {f['archivo'] for f in F}
sobran = [a for a in os.listdir('assets/fondos') if 'assets/fondos/' + a not in usados]
print('fondos aplicados:', {p: [f['archivo'].split('/')[-1] for f in fs] for p, fs in pages.items()}, '| sin usar:', sobran)
