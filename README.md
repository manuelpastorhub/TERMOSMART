# 🌡️ Termosmart

**Motor de decisión para prevención de golpe de calor en deportistas de resistencia, diseñado para wearables.**

En lugar de fiarse de un único sensor de temperatura de muñeca (poco fiable como proxy de temperatura central), Termosmart combina una **estimación mecánica de temperatura central** con un **detector de deriva cardiovascular basado en tendencia temporal**, contrastados con el estrés térmico ambiental (WBGT).

```
min 5  → core=38.2°C  AMARILLO: fatiga térmica inicial
min 8  → core=39.0°C  ROJO: cese inmediato de la actividad
```

---

## El problema que resuelve

Los relojes deportivos miden temperatura cutánea de muñeca, no temperatura central — que es la que define clínicamente el riesgo de golpe de calor. La correlación entre ambas es débil: la piel se calienta y se enfría por vasodilatación/vasoconstricción independientemente de lo que esté pasando en el core. Un sistema de alerta que dispare solo con ese sensor genera falsos positivos (calor ambiental sin riesgo real) y falsos negativos (core subiendo mientras la muñeca no lo refleja).

## Cómo lo aborda Termosmart

En vez de medir lo que no se puede medir bien, **estima** lo que sí es causalmente relevante:

| Señal | Qué mide | Cómo se calcula |
|---|---|---|
| **WBGT ambiental** | Estrés térmico del entorno | Aproximación BOM (temperatura, humedad real vía presión de vapor, radiación, viento) |
| **Temperatura central estimada** | Balance calórico interno | Producción metabólica (ecuación ACSM: velocidad + desnivel) menos disipación (limitada por WBGT y por la propia respuesta termorreguladora) |
| **Deriva cardiovascular** | Estrés térmico interno no explicado por el esfuerzo | Regresión de la tendencia de FC en el tiempo, solo quando la carga externa se mantiene estable, descartando el pico simpático inicial (~90s) |
| **Muñeca (secundaria)** | Confirmación periférica | Solo escala una alerta ya existente, nunca dispara por sí sola |

Cada señal es independiente — no se fusionan en un único número "de confianza ciega". Se combinan con lógica booleana explícita en `evaluar_riesgo_termosmart`, diseñada para que **el calor ambiental por sí solo nunca dispare la alarma** (evita falsos positivos en deportistas aclimatados).

### Alertas: estado persistente vs. aviso puntual

El reloj no debe comportarse igual en riesgo que fuera de riesgo. `HisteresisAlerta` distingue explícitamente:

- **AMARILLO / ROJO** son **estados persistentes**: se activan con un evento puntual (`ENTRA_AMARILLO` / `ENTRA_ROJO`) y se mantienen visibles mientras dure el riesgo, sin generar avisos repetidos en cada lectura.
- **Volver a valores seguros** es un **evento puntual único** (`VUELVE_A_NORMALIDAD`, "puedes continuar con normalidad"), no un estado — tras el aviso, el sistema vuelve al silencio (`NORMAL`) y no repite nada mientras todo vaya bien.
- Escalar exige pocas lecturas consecutivas (por defecto 2); volver a normalidad exige más (por defecto 4) — **escalar rápido, desescalar despacio**, principio de seguridad estándar en este tipo de sistemas.

### Frecuencias de muestreo: no todo va al mismo ritmo

Es tentador pensar en "todo en tiempo real a la vez", pero no es así ni tiene por qué serlo — cada señal cambia a una velocidad físicamente distinta:

- **FC y pendiente/velocidad**: casi continuas, alimentan el estimador de core y el detector de deriva cada pocos segundos (datos on-device: sensor óptico + GPS/barómetro).
- **WBGT ambiental**: cambia en minutos/horas, no en segundos. Recalcularlo cada segundo sería inútil y costoso en batería/red si depende de una API externa. Se recalcula con mucha menos frecuencia y se reutiliza el último valor conocido entre medias — el código ya está preparado para esto (`wbgt_ambiental` se pasa como parámetro, no se recalcula internamente).

Este desfase de frecuencias es precisamente el hueco donde encajará la futura integración con una API de geolocalización/clima (pendiente, ver más abajo).

## Por qué esto y no otra cosa (decisiones de diseño)

Este proyecto se construyó auditando y descartando activamente varios enfoques más "impresionantes" en apariencia:

- ❌ **Filtro de Kalman con corrección por FC vs. curva calibrada por atleta** — descartado: exigía una curva de FC esperada por deportista que no existe sin datos de campo reales. Mantenerlo habría aparentado una precisión que el modelo no tiene.
- ✅ **Detector de deriva cardiovascular por tendencia temporal** — en su lugar: no necesita saber la FC "correcta" de nadie de antemano, solo si sube sin motivo mecánico mientras la carga se mantiene constante. Es una comparación relativa dentro de la propia sesión, y coincide con cómo se estudia la deriva cardiovascular en literatura de fisiología del ejercicio.

## Tests

29 tests con `pytest`, cubriendo específicamente las decisiones de diseño del proyecto (no solo "que no explote"):

```bash
pytest test_termosmart_motor_riesgo.py -v
```

| Qué se prueba | Por qué importa |
|---|---|
| WBGT usa presión de vapor real, no humedad cruda | Es el bug original que se corrigió — si reaparece, el test lo detecta |
| Core sube más rápido con más velocidad/pendiente | Coherencia física básica del estimador |
| Deriva cardiovascular se detecta con FC sostenida + carga estable + calor | El caso que sí debe dispararse |
| Pico de adrenalina al arrancar NO dispara deriva | Falso positivo explícitamente evitado por diseño |
| Calor ambiental solo, sin respuesta interna, da VERDE | Requisito central del proyecto desde el primer diseño |
| Histéresis no escala con una lectura aislada de ruido | Evita parpadeo de alertas |
| Estado persistente no genera eventos repetidos en cada lectura | AMARILLO/ROJO se mantienen sin spamear avisos |
| Volver a normalidad es un evento único, no un estado repetido | El requisito de "aviso puntual, no VERDE todo el rato" |
| Validaciones de entrada (pesos, FC, humedad fuera de rango) | Lanzan `ValueError` en vez de comportamiento indefinido |

## Estado del proyecto — honestidad ante todo

Esto es un **motor de decisión de apoyo, no un dispositivo diagnóstico**. Concretamente:

- Las constantes físicas (capacidad de disipación corporal, umbrales de deriva de FC, duración de ventanas) son **placeholders de ingeniería razonables**, no coeficientes clínicamente validados. Un despliegue real exigiría calibrarlos contra temperatura central medida (cápsula ingerible o rectal) en protocolo de laboratorio.
- La temperatura de muñeca se usa deliberadamente como señal débil/secundaria, no como disparador, por su correlación limitada con temperatura central real.
- No sustituye criterio médico ni la percepción subjetiva del propio deportista.

## Próximos pasos

- [x] Suite de tests (`pytest`) cubriendo casos límite: pico de adrenalina, WBGT extremo, sensores inválidos
- [x] Histéresis temporal para evitar parpadeo de alertas, con modelo evento/estado (aviso puntual vs. alerta persistente)
- [ ] Integración con API de geolocalización/clima para WBGT en tiempo real (por coordenadas, no por ciudad, corrigiendo por altitud)
- [ ] Arquitectura de actualización a distintas frecuencias (FC/GPS a alta frecuencia, WBGT a baja frecuencia)
- [ ] Manejo de lecturas nulas/outliers de sensores reales
- [ ] Protocolo de calibración de constantes con datos de campo

## Uso

```python
from termosmart_motor_riesgo import (
    calcular_wbgt_estandar,
    EstimadorTemperaturaCentral,
    DetectorDerivaCardiovascular,
    HisteresisAlerta,
    evaluar_riesgo_termosmart,
)

wbgt = calcular_wbgt_estandar(temp_aire=32.0, humedad=70.0,
                               radiacion_solar=600, velocidad_viento=1.5)

estimador = EstimadorTemperaturaCentral(peso_kg=75)
detector = DetectorDerivaCardiovascular()
histeresis = HisteresisAlerta()

# En cada tick del reloj (p. ej. cada 60s):
core = estimador.actualizar(dt_seg=60, velocidad_kmh=13.0,
                             pendiente_pct=2.0, wbgt_ambiental=wbgt)
deriva = detector.actualizar(dt_seg=60, velocidad_kmh=13.0, pendiente_pct=2.0,
                              fc_actual=168, wbgt_ambiental=wbgt)
resultado = evaluar_riesgo_termosmart(
    temp_core_estimada=core, temp_muneca=33.9,
    fc_actual=168, fc_max=190,
    deriva_cardiovascular=deriva, wbgt_ambiental=wbgt,
)

evento, estado_activo, mensaje = histeresis.procesar(resultado)
if evento:
    print(f"[{evento}] {mensaje}")   # notificar al usuario, una sola vez
elif estado_activo:
    pass  # mantener el banner de alerta en pantalla, sin nuevo aviso
```

## Stack

Python 3, sin dependencias externas.

---

*Proyecto personal de portfolio. Fundamentos citados: aproximación WBGT de la Oficina de Meteorología australiana (BOM); ecuación de coste metabólico de carrera de ACSM; deriva cardiovascular en ejercicio prolongado (Coyle & González-Alonso, 2001).*
