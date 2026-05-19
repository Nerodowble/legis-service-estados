"""Exceções customizadas do legis-service-estados."""


class ALIndisponivelError(Exception):
    """A AL retornou erro (502/503/504/timeout/conn refused)."""

    def __init__(self, uf: str, status: int | None, motivo: str):
        self.uf = uf
        self.status = status
        self.motivo = motivo
        super().__init__(f"AL {uf} indisponível (status {status}): {motivo}")


class ALBloqueadaError(Exception):
    """A AL existe mas não permite acesso programático (RN, MG)."""

    def __init__(self, uf: str, motivo_legal: str):
        self.uf = uf
        self.motivo_legal = motivo_legal
        super().__init__(f"AL {uf} bloqueada: {motivo_legal}")


class ProposicaoNaoEncontradaError(Exception):
    """ID/slug informado não corresponde a nenhuma proposição na AL."""

    def __init__(self, uf: str, id_fonte: str):
        self.uf = uf
        self.id_fonte = id_fonte
        super().__init__(f"Proposição {id_fonte} não encontrada em {uf}")


class ParserFalhouError(Exception):
    """O parser específico da AL não conseguiu interpretar a resposta da fonte."""

    def __init__(self, uf: str, detalhe: str):
        self.uf = uf
        self.detalhe = detalhe
        super().__init__(f"Parser falhou para {uf}: {detalhe}")
