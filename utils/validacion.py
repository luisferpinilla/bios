class Validacion():
    def __init__(self, severidad: str, mensaje: str) -> None:
        self._severidad = severidad
        self._mensaje = mensaje

    def __str__(self) -> str:
        return f'{self._severidad}: {self._mensaje}'

    def get_severidad(self):
        return self._severidad

    def get_mensaje(self):
        return self._mensaje
