"""
Matriz de capacidade por AL.

Define, para cada adapter, quais campos da `ProposicaoNormalizadaRaw` a fonte
upstream realmente expõe. Os testes de completude usam esta matriz para
verificar que estamos extraindo todo o conteúdo disponível.

Convenção:
  OBRIGATORIO  → adapter DEVE preencher (caso contrário falha de qualidade)
  OPCIONAL     → adapter pode preencher (depende do item específico)
  NAO_DISPONIVEL → fonte upstream não expõe o dado (deve ficar null)
"""

from __future__ import annotations

from dataclasses import dataclass, field

OBRIGATORIO = "OBRIGATORIO"
OPCIONAL = "OPCIONAL"
NAO_DISPONIVEL = "NAO_DISPONIVEL"


@dataclass
class CapacidadeAL:
    """Campos esperados na resposta da LISTAGEM de um adapter."""

    source_id: str
    uf: str
    casa_identificadora: str
    # Campos da ProposicaoNormalizadaRaw
    id_proposicao_origem: str = OBRIGATORIO
    sigla_tipo: str = OBRIGATORIO
    numero: str = OBRIGATORIO
    ano: str = OBRIGATORIO
    ementa: str = OPCIONAL
    data_apresentacao: str = OPCIONAL
    status: str = NAO_DISPONIVEL
    url_inteiro_teor: str = OPCIONAL
    autores: str = OPCIONAL  # se OBRIGATORIO, ao menos 1 autor com nome
    autor_partido: str = NAO_DISPONIVEL
    autor_id: str = NAO_DISPONIVEL
    tramitacoes: str = NAO_DISPONIVEL
    codigo_materia: str = NAO_DISPONIVEL
    objetivo: str = NAO_DISPONIVEL
    # Campos do detail (quando o adapter tem detalhe enriquecido)
    detalhe_implementado: bool = False
    notas: list[str] = field(default_factory=list)


CAPACIDADES: dict[str, CapacidadeAL] = {
    "al_ap": CapacidadeAL(
        source_id="al_ap",
        uf="AP",
        casa_identificadora="ALAP",
        id_proposicao_origem=OBRIGATORIO,
        sigla_tipo=OBRIGATORIO,
        numero=OBRIGATORIO,
        ano=OBRIGATORIO,
        ementa=OBRIGATORIO,
        data_apresentacao=OBRIGATORIO,
        url_inteiro_teor=OBRIGATORIO,
        autores=OBRIGATORIO,
        autor_partido=OPCIONAL,  # via tooltip da página de parlamentares
        autor_id=OPCIONAL,
        tramitacoes=OPCIONAL,  # só no detalhe
        codigo_materia=OBRIGATORIO,  # fallback = id_origem
        objetivo=OPCIONAL,  # legislatura, só no detalhe
        detalhe_implementado=True,
        notas=[
            "Listagem usa <tbody><tr> com 5 cells",
            "Detalhe acrescenta tramitações + legislatura",
        ],
    ),
    "al_ba": CapacidadeAL(
        source_id="al_ba",
        uf="BA",
        casa_identificadora="ALBA",
        id_proposicao_origem=OBRIGATORIO,  # slug TIPO-NUM-ANO
        sigla_tipo=OBRIGATORIO,
        numero=OBRIGATORIO,
        ano=OBRIGATORIO,
        ementa=OPCIONAL,
        url_inteiro_teor=OBRIGATORIO,
        autores=NAO_DISPONIVEL,  # listagem só dá slugs, não autor
        data_apresentacao=NAO_DISPONIVEL,
        detalhe_implementado=True,
        notas=["Listagem só extrai slugs canônicos; detalhe enriquece"],
    ),
    "al_ce": CapacidadeAL(
        source_id="al_ce",
        uf="CE",
        casa_identificadora="ALECE",
        ementa=OBRIGATORIO,
        data_apresentacao=OBRIGATORIO,
        autores=OBRIGATORIO,
        url_inteiro_teor=OPCIONAL,
        detalhe_implementado=True,
        notas=[
            "PHP legado UTF-8 (declara ISO-8859-1 mas serve UTF-8)",
            "Parser de TRs adjacentes (item ocupa 6 TRs)",
            "Detalhe: filtra listagem por (numero, ano) — não há endpoint per-item",
        ],
    ),
    "al_df": CapacidadeAL(
        source_id="al_df",
        uf="DF",
        casa_identificadora="CLDF",
        id_proposicao_origem=OBRIGATORIO,  # slug TIPO_NUM_ANO
        sigla_tipo=OBRIGATORIO,
        numero=OBRIGATORIO,
        ano=OBRIGATORIO,
        ementa=NAO_DISPONIVEL,  # só vem no detalhe
        autores=NAO_DISPONIVEL,
        data_apresentacao=NAO_DISPONIVEL,
        url_inteiro_teor=OBRIGATORIO,
        detalhe_implementado=True,
        notas=["Liferay; listagem só tem slugs; detalhe tem ementa"],
    ),
    "al_ma": CapacidadeAL(
        source_id="al_ma",
        uf="MA",
        casa_identificadora="ALEMA",
        ementa=OBRIGATORIO,  # extraída por regex do content.rendered
        data_apresentacao=OPCIONAL,
        url_inteiro_teor=OBRIGATORIO,
        autores=OPCIONAL,  # autor agora estruturado (Deputado/Executivo/Mesa/Comissão)
        detalhe_implementado=True,
        notas=[
            "WordPress REST; PLs vêm dentro de Ordens do Dia (HTML embarcado)",
            "Autor classificado: Deputado, Executivo (Poder Executivo), Comissao (Mesa, Comissão, Bancada)",
            "Detalhe: filtra ordens do ano alvo por (sigla, numero, ano)",
        ],
    ),
    "al_mt": CapacidadeAL(
        source_id="al_mt",
        uf="MT",
        casa_identificadora="ALMT",
        id_proposicao_origem=OBRIGATORIO,
        sigla_tipo=OPCIONAL,  # só no detalhe (HermesLegis <title>)
        numero=OPCIONAL,
        ano=OPCIONAL,
        ementa=NAO_DISPONIVEL,  # só HTML pesado da página de detalhe tem
        data_apresentacao=NAO_DISPONIVEL,
        url_inteiro_teor=OBRIGATORIO,
        autores=OPCIONAL,  # extraído do <title> via regex
        status=OPCIONAL,
        detalhe_implementado=True,
        notas=["HermesLegis Symfony; listagem só dá IDs; detalhe parseia <title>"],
    ),
    "al_pa": CapacidadeAL(
        source_id="al_pa",
        uf="PA",
        casa_identificadora="ALEPA",
        ementa=OBRIGATORIO,
        data_apresentacao=OBRIGATORIO,
        autores=OBRIGATORIO,
        status=OBRIGATORIO,  # sempre "Em tramitação" no CallbackPanelProposicoes
        url_inteiro_teor=OBRIGATORIO,
        detalhe_implementado=True,
        notas=[
            "DevExpress; cards .card-proposicao com h3/span/p",
            "Detalhe: /Legislativo/DetalhesProposicao?IdProposicao=N",
            "Detalhe enriquece com regime, situação, anexos PDF",
        ],
    ),
    "al_pe": CapacidadeAL(
        source_id="al_pe",
        uf="PE",
        casa_identificadora="ALEPE",
        ementa=OBRIGATORIO,
        data_apresentacao=OBRIGATORIO,
        autores=OBRIGATORIO,
        detalhe_implementado=True,
        notas=[
            "XML público com atributos no <projeto>",
            "Detalhe: filtra docid no XML completo (sem endpoint per-item)",
        ],
    ),
    "al_rj": CapacidadeAL(
        source_id="al_rj",
        uf="RJ",
        casa_identificadora="ALERJ",
        sigla_tipo=OPCIONAL,
        numero=OPCIONAL,
        ano=OPCIONAL,
        ementa=OPCIONAL,
        data_apresentacao=OPCIONAL,
        url_inteiro_teor=OBRIGATORIO,
        autores=OPCIONAL,
        status=OPCIONAL,
        detalhe_implementado=True,
        notas=[
            "IBM Lotus Notes; XML com columnnumber",
            "Detalhe: GET {base}.nsf/{UNID}?OpenDocument (tenta 3 bases: scpro2327, scpro, contlei)",
        ],
    ),
    "al_sc": CapacidadeAL(
        source_id="al_sc",
        uf="SC",
        casa_identificadora="ALESC",
        id_proposicao_origem=OBRIGATORIO,  # hash curto
        url_inteiro_teor=OBRIGATORIO,
        ementa=OPCIONAL,  # texto do link "PL./0216/2024"
        autores=NAO_DISPONIVEL,  # só no detalhe
        data_apresentacao=NAO_DISPONIVEL,
        detalhe_implementado=True,
        notas=["eLegis CakePHP; listagem só tem hashes; detalhe parseia <title>"],
    ),
    "al_sp": CapacidadeAL(
        source_id="al_sp",
        uf="SP",
        casa_identificadora="ALESP",
        ementa=OBRIGATORIO,
        data_apresentacao=OBRIGATORIO,
        autores=NAO_DISPONIVEL,  # proposituras.xml NÃO inclui autor (vem em autores.zip)
        url_inteiro_teor=OBRIGATORIO,
        codigo_materia=OBRIGATORIO,  # = IdDocumento
        detalhe_implementado=True,
        notas=[
            "Dumps ZIP/XML; streaming-parse de <propositura>",
            "Estrutura real: AnoLegislativo, IdDocumento, IdNatureza, NroLegislativo, Ementa, DtPublicacao",
            "Autor NÃO está em proposituras.xml; cruzar com autores.zip seria etapa futura",
            "Detalhe: streaming-parse + filtro por IdDocumento (mesmo download que listagem)",
        ],
    ),
}
