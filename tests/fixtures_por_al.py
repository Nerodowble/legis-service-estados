"""
Fixtures HTML/XML mínimas mas REALISTAS para cada uma das 11 ALs.

Cada fixture replica a estrutura observada AO VIVO nas fontes upstream
durante o levantamento (`docs/levantamento_assembleias.md` + capturas
reais durante esta sessão). NÃO usar dados imaginários — todos os formatos
vêm de observação direta.
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────
# al_ap — eLegis Laravel SSR (https://elegis.al.ap.leg.br)
# ──────────────────────────────────────────────────────────────────────

ALAP_LISTAGEM = """<!DOCTYPE html><html><head></head><body>
<table><tbody>
  <tr>
    <td>19/05/2026</td>
    <td>Moção nº 0317/26-AL</td>
    <td>Deputado Rodolfo Vale</td>
    <td>Moção de Aplauso aos profissionais listados no anexo único.</td>
    <td><a href="https://elegis.al.ap.leg.br/portal/proposicao/108457">Visualizar</a></td>
  </tr>
  <tr>
    <td>18/05/2026</td>
    <td>Projeto de Lei Ordinária nº 0042/2026</td>
    <td>Deputada Aldilene Souza</td>
    <td>Dispõe sobre transporte escolar gratuito.</td>
    <td><a href="https://elegis.al.ap.leg.br/portal/proposicao/108400">Visualizar</a></td>
  </tr>
</tbody></table>
</body></html>"""

ALAP_PARLAMENTARES = """<!DOCTYPE html><html><body>
<div class="ls-box">
  <div class="box-foto-deputados">
    <a href="pagina.php?pg=exibir_parlamentar&amp;iddeputado=74" onmouseover="Tip('<b>Dep.</b> Aldilene Souza<br><b>Nome Completo:</b> ALDILENE MATOS DE SOUZA<br><b>Partido:</b> PDT<br><b>Profissão:</b> Administradora', WIDTH, 200)">
      <img src="aldilene.jpg">
    </a>
  </div>
</div>
<div class="ls-box">
  <div class="box-foto-deputados">
    <a href="pagina.php?pg=exibir_parlamentar&amp;iddeputado=95" onmouseover="Tip('<b>Dep.</b> Rodolfo Vale<br><b>Nome Completo:</b> RODOLFO SOUSA FOLHA DO VALE<br><b>Partido:</b> UNIÃO BRASIL<br><b>Profissão:</b> Bacharel em Direito', WIDTH, 200)">
      <img src="rodolfo.jpg">
    </a>
  </div>
</div>
</body></html>"""

# ──────────────────────────────────────────────────────────────────────
# al_ba — Portal ALBA atividade-legislativa-nova
# ──────────────────────────────────────────────────────────────────────

ALBA_LISTAGEM = """<!DOCTYPE html><html><body>
<div class="lista">
  <a href="/atividade-legislativa-nova/proposicao/REQ-10650-2025">REQ 10650/2025</a>
  <a href="/atividade-legislativa-nova/proposicao/PL-1234-2024">PL 1234/2024</a>
</div>
</body></html>"""

# ──────────────────────────────────────────────────────────────────────
# al_ce — ALECE PHP legado ISO-8859-1
# ──────────────────────────────────────────────────────────────────────

ALECE_LISTAGEM = (
    """<!DOCTYPE html><html><body>
<table><tr><td>
Nº do Proj.: 1234/24
Autor: Deputado João Silva
Entrada: 15.03.24
Ementa: Dispõe sobre subsídio ao petróleo no Estado do Ceará.
Nº do Proj.: 1235/24
Autor: Deputada Maria Souza
Entrada: 20.03.24
Ementa: Regulamenta o transporte escolar municipal.
</td></tr></table>
</body></html>""".encode("iso-8859-1")
)

# ──────────────────────────────────────────────────────────────────────
# al_df — CLDF Liferay
# ──────────────────────────────────────────────────────────────────────

ALDF_LISTAGEM = """<!DOCTYPE html><html><body>
<div>
  <a href="/proposicao/-/documentos/PL_1495_2025">PL 1495/2025</a>
  <a href="/proposicao/-/documentos/MO_746_2024">MO 746/2024</a>
  <a href="/proposicao/-/documentos/IND_10447_2026">IND 10447/2026</a>
</div>
</body></html>"""

# ──────────────────────────────────────────────────────────────────────
# al_ma — WordPress REST API (al.ma.leg.br/sitealema)
# ──────────────────────────────────────────────────────────────────────

ALMA_JSON = [
    {
        "id": 1,
        "date": "2024-03-15T10:00:00",
        "link": "https://www.al.ma.leg.br/ordem/1",
        "content": {
            "rendered": (
                "<p>PROJETO DE LEI ORDINÁRIA Nº 030/2024, DE AUTORIA DO DEPUTADO "
                "FULANO DA SILVA QUE dispõe sobre a criação de programa estadual.</p>"
                "<p>PROJETO DE LEI Nº 031/2024, DE AUTORIA DA DEPUTADA MARIA QUE "
                "regulamenta o transporte público.</p>"
            )
        },
    }
]

# ──────────────────────────────────────────────────────────────────────
# al_mt — HermesLegis Symfony
# ──────────────────────────────────────────────────────────────────────

ALMT_LISTAGEM = """<!DOCTYPE html><html><body>
<a href="/proposicao/cpdoc/172857/visualizar">Proposição</a>
<a href="/proposicao/cpdoc/171138/visualizar">Proposição</a>
</body></html>"""

ALMT_DETALHE = """<!DOCTYPE html><html>
<head><title>Projeto de lei nº 42/2026 Dep. Eduardo Botelho - Projeto em Tramitação</title></head>
<body></body></html>"""

# ──────────────────────────────────────────────────────────────────────
# al_pa — ALEPA DevExpress (.card-proposicao)
# ──────────────────────────────────────────────────────────────────────

ALEPA_LISTAGEM = """<!DOCTYPE html><html><body>
<p>2 Resultados</p>
<div class="card-proposicao" onclick="onCardClick('/Legislativo/DetalhesProposicao?IdProposicao=14341&tipo=INDICA%C3%87%C3%83O&situacao=1')">
  <h3>DEP. LÍVIA DUARTE</h3>
  <span>INDICAÇÃO Nº 142/2024, DE 18/12/2024</span>
  <p>Requer ao Governador a criação do Programa Estadual de Educação em Direitos Humanos.</p>
</div>
<div class="card-proposicao" onclick="onCardClick('/Legislativo/DetalhesProposicao?IdProposicao=14340&tipo=PROJETO%20DE%20LEI&situacao=1')">
  <h3>DEP. BRAZ</h3>
  <span>PROJETO DE LEI Nº 100/2024, DE 10/01/2024</span>
  <p>Cria a Política Paraense de Prevenção das Mortes Violentas.</p>
</div>
</body></html>"""

# ──────────────────────────────────────────────────────────────────────
# al_pe — ALEPE XML (dadosabertos)
# ──────────────────────────────────────────────────────────────────────

ALEPE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<projetos>
  <projeto docid="13539" numero="3" ano="2024" tipo="PROJETO DE LEI ORDINARIA"
           ementa="Dispoe sobre subsidio ao petroleo" dataPublicacao="14/06/2024">
    <autores><autor nome="Coronel Alberto Feitosa" tipo="DEPUTADO"/></autores>
  </projeto>
  <projeto docid="13540" numero="4" ano="2024" tipo="PROJETO DE LEI COMPLEMENTAR"
           ementa="Educacao infantil" dataPublicacao="20/06/2024">
    <autores><autor nome="Mesa Diretora" tipo="COMISSAO"/></autores>
  </projeto>
</projetos>"""

# ──────────────────────────────────────────────────────────────────────
# al_rj — ALERJ Lotus Notes (XML com columnnumber)
# ──────────────────────────────────────────────────────────────────────

ALERJ_XML = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
<viewentries toplevelentries="2">
  <viewentry position="1" unid="ABC123">
    <entrydata columnnumber="0"><text>PL 1234/2024</text></entrydata>
    <entrydata columnnumber="1"><text>15/03/2024</text></entrydata>
    <entrydata columnnumber="2"><text>Deputado Carlos Macedo</text></entrydata>
    <entrydata columnnumber="3"><text>Dispoe sobre incentivo cultural</text></entrydata>
    <entrydata columnnumber="4"><text>Em tramitacao</text></entrydata>
  </viewentry>
  <viewentry position="2" unid="DEF456">
    <entrydata columnnumber="0"><text>PL 1235/2024</text></entrydata>
    <entrydata columnnumber="1"><text>16/03/2024</text></entrydata>
    <entrydata columnnumber="2"><text>Deputada Ana Lima</text></entrydata>
    <entrydata columnnumber="3"><text>Regulamenta transporte</text></entrydata>
    <entrydata columnnumber="4"><text>Aprovado</text></entrydata>
  </viewentry>
</viewentries>"""

# ──────────────────────────────────────────────────────────────────────
# al_sc — eLegis ALESC htmx + hash curto
# ──────────────────────────────────────────────────────────────────────

ALESC_LISTAGEM = """<!DOCTYPE html><html><body>
<div>
  <a href="/proposicoes/N0MQP/tramitacoes">PL./0216/2024</a>
  <a href="/proposicoes/5Z1Q7/tramitacoes">PL./0324/2026</a>
  <a href="/proposicoes/X3KT9/tramitacoes">PEC./0005/2023</a>
</div>
</body></html>"""

# ──────────────────────────────────────────────────────────────────────
# al_sp — ALESP dump ZIP/XML
# ──────────────────────────────────────────────────────────────────────

import io
import zipfile


def alesp_zip_bytes() -> bytes:
    """Cria um ZIP em memória com proposituras.xml mínimo."""
    xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<proposituras>
  <propositura>
    <id>9999</id>
    <siglaTipo>PL</siglaTipo>
    <numero>1</numero>
    <anoLegislativo>2024</anoLegislativo>
    <ementa>Cria programa de incentivo ambiental em SP.</ementa>
    <dataEntrada>2024-03-15</dataEntrada>
    <nomeAutor>Deputado Ricardo Santos</nomeAutor>
  </propositura>
  <propositura>
    <id>9998</id>
    <siglaTipo>PEC</siglaTipo>
    <numero>2</numero>
    <anoLegislativo>2024</anoLegislativo>
    <ementa>Altera Constituicao Estadual.</ementa>
    <dataEntrada>2024-04-20</dataEntrada>
    <nomeAutor>Mesa Diretora</nomeAutor>
  </propositura>
</proposituras>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("proposituras.xml", xml_content)
    return buf.getvalue()
