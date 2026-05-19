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
<table>
  <tr class="table-itens">
    <td class="mapa">
      <a href="/atividade-legislativa-nova/proposicao/REQ-10650-2025">
        <span>REQ/10650/2025</span>
      </a>
    </td>
    <td><span class="fe-html-ativ">Dispõe sobre a validade indeterminada do laudo médico que ateste o Diabetes Mellitus Tipo 1.</span></td>
    <td><a href="https://www.al.ba.gov.br/docs/REQ-10650-2025.pdf">Texto Original</a></td>
  </tr>
  <tr class="table-itens">
    <td class="mapa">
      <a href="/atividade-legislativa-nova/proposicao/PL-1234-2024">
        <span>PL/1234/2024</span>
      </a>
    </td>
    <td><span class="fe-html-ativ">Cria programa estadual de incentivo à leitura.</span></td>
    <td><a href="https://www.al.ba.gov.br/docs/PL-1234-2024.pdf">Texto Original</a></td>
  </tr>
</table>
</body></html>"""

# ──────────────────────────────────────────────────────────────────────
# al_ce — ALECE PHP legado ISO-8859-1
# ──────────────────────────────────────────────────────────────────────

ALECE_LISTAGEM = """<!DOCTYPE html><html><body>
<table>
  <tr><td>Exibindo registros 1 a 20 (de 2355)Página 1 de 118</td></tr>
  <tr><td>Nº do Proj.:1234/24 Autor:DEPUTADO JOÃO SILVA Entrada:15.03.24 Expediente:20.03.24</td></tr>
  <tr><td>Nº do Proj.:1234/24 Autor:DEPUTADO JOÃO SILVA Entrada:15.03.24 Expediente:20.03.24</td></tr>
  <tr><td>Ementa:Dispõe sobre subsídio ao petróleo no Estado do Ceará.Descrição:</td></tr>
  <tr><td>Ementa:Dispõe sobre subsídio ao petróleo no Estado do Ceará.</td></tr>
  <tr><td>Descrição:</td></tr>
  <tr><td>Distribuição/Comissões:CCJR/CASLocalização:CCJREm 15.03.24 - Departamento LegislativoEm 20.03.24 - Leitura no Expediente</td></tr>

  <tr><td>Nº do Proj.:1235/24 Autor:DEPUTADA MARIA SOUZA Entrada:20.03.24</td></tr>
  <tr><td>Nº do Proj.:1235/24 Autor:DEPUTADA MARIA SOUZA Entrada:20.03.24</td></tr>
  <tr><td>Ementa:Regulamenta o transporte escolar municipal.Descrição:</td></tr>
  <tr><td>Ementa:Regulamenta o transporte escolar municipal.</td></tr>
  <tr><td>Descrição:</td></tr>
  <tr><td>Distribuição/Comissões:CTASPLocalização:CTASPEm 20.03.24 - Departamento Legislativo</td></tr>
</table>
</body></html>""".encode()

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
<div class="col-12">
  <h3 class="fs-16">VETO PARCIAL APOSTO AO PROJETO DE LEI Nº 864/2023, QUE DISPÕE SOBRE A INSTITUIÇÃO DO CADASTRO ESTADUAL DE PESSOAS ACOMETIDAS DE DOENÇAS RARAS. AUTORES: DEPUTADO DIEGO GUIMARÃES E DEPUTADO EDUARDO BOTELHO</h3>
  <div class="text-muted mb-2">Veto nº 1/2026 Mensagem nº 170/2025 - Protocolo nº 871/2026</div>
  <div id="collapse-group-172857">
    <a href="/proposicao/cpdoc/172857/visualizar">Visualizar</a>
  </div>
</div>
<div class="col-12">
  <h3 class="fs-16">PROJETO DE LEI Nº 42/2026, QUE INSTITUI POLÍTICA ESTADUAL X. AUTOR: DEPUTADO EDUARDO BOTELHO</h3>
  <div class="text-muted mb-2">Projeto de Lei nº 42/2026</div>
  <div id="collapse-group-171138">
    <a href="/proposicao/cpdoc/171138/visualizar">Visualizar</a>
  </div>
</div>
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
    """
    Cria um ZIP em memória com proposituras.xml mínimo.
    Estrutura REAL validada ao vivo (2026-05-19) do dump ALESP.
    """
    xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<proposituras>
  <propositura>
    <AnoLegislativo>2024</AnoLegislativo>
    <CodOriginalidade>                              </CodOriginalidade>
    <Ementa>Cria programa de incentivo ambiental em SP.</Ementa>
    <DtEntradaSistema>2024-03-15T00:00:00-03:00</DtEntradaSistema>
    <DtPublicacao>2024-03-15T00:00:00-03:00</DtPublicacao>
    <IdDocumento>9999</IdDocumento>
    <IdNatureza>1</IdNatureza>
    <NroLegislativo>1</NroLegislativo>
  </propositura>
  <propositura>
    <AnoLegislativo>2024</AnoLegislativo>
    <CodOriginalidade>                              </CodOriginalidade>
    <Ementa>Altera Constituicao Estadual.</Ementa>
    <DtEntradaSistema>2024-04-20T00:00:00-03:00</DtEntradaSistema>
    <DtPublicacao>2024-04-20T00:00:00-03:00</DtPublicacao>
    <IdDocumento>9998</IdDocumento>
    <IdNatureza>3</IdNatureza>
    <NroLegislativo>2</NroLegislativo>
  </propositura>
</proposituras>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("proposituras.xml", xml_content)
    return buf.getvalue()
