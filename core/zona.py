"""La zona horaria del negocio, escrita UNA vez.

Estaba escrita TRES —app/main.py, app/costeo.py y core/casilla_pedidos.py—
y las tres como un OFFSET NUMÉRICO fijo de menos tres horas, no como una
zona. Hoy da lo mismo porque Argentina no mueve el reloj desde 2009.

El día que lo mueva, un offset fijo no se entera: sigue diciendo −3 cuando
son −2, y lo hace en silencio y en tres lugares a la vez. `ZoneInfo` lee la
base de datos de zonas del sistema y acompaña el cambio solo.

Es la misma regla que en el SQL, donde la zona va nombrada (37 veces) y
nunca un intervalo de horas suelto. Que las dos mitades del sistema nombren la MISMA zona —y no un número que
hoy coincide— es lo que las mantiene juntas el día que el número cambie.
"""

from zoneinfo import ZoneInfo

NOMBRE_ZONA = "America/Argentina/Buenos_Aires"

ARGENTINA = ZoneInfo(NOMBRE_ZONA)
