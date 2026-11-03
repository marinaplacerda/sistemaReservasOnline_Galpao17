class ErrosSistema(Exception):
    codigo_http = 400;

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem);
        self.mensagem = mensagem;

class ErroDeNegocio(ErrosSistema):
    codigo_http = 409;

class PermissaoNegada(ErroDeNegocio):
    codigo_http = 403;

class NaoEncontrado(ErrosSistema):
    codigo_http = 404;