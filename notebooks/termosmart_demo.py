# Instalación de dependencias (necesario si alguien lo ejecuta en un entorno limpio)
# Nota: En un script .py puro, los comandos con '!' pueden dar error. 
# Lo ideal es que el usuario las instale desde la terminal, pero lo dejamos documentado.
import os
os.system('pip install requests matplotlib')

import sys
import matplotlib.pyplot as plt

# Permite que el script encuentre la carpeta src que está un nivel arriba
sys.path.append('../src')

from termosmart import (
    ProveedorMeteo,
    calcular_wbgt_estandar,
    EstimadorTemperaturaCentral,
    DetectorDerivaCardiovascular,
    evaluar_riesgo_termosmart,
    HisteresisAlerta
)

print("--- INICIANDO LECTOR DE SESIÓN Y GENERACIÓN DE GRÁFICA ---")

# 1. Conexión a la API Open-Meteo
api_meteo = ProveedorMeteo(latitud=40.4168, longitud=-3.7038)
temp, hum, viento, radiacion, altitud = api_meteo.obtener_datos_entorno()
if temp < 28.0:
    temp, hum, viento, radiacion = 32.0, 65.0, 1.5, 600

wbgt_real = calcular_wbgt_estandar(temp, hum, radiacion, viento)
print(f"WBGT Ambiental calculado: {wbgt_real} ºC")

# 2. Inicializar motores
estimador = EstimadorTemperaturaCentral(peso_kg=75, temp_core_inicial=37.0)
detector_deriva = DetectorDerivaCardiovascular()
histeresis = HisteresisAlerta()

# 3. Datos simulados de entrenamiento (CSV)
sesion_csv_simulada = [
    [1,  12.0, 0.0, 140, 32.0],
    [5,  12.0, 0.0, 145, 32.5],
    [10, 12.0, 4.0, 165, 32.8],
    [15, 12.0, 4.0, 168, 33.0],
    [20, 12.0, 0.0, 150, 33.2],
    [25, 12.0, 0.0, 155, 33.5],
    [30, 12.0, 0.0, 162, 33.8],
    [35, 12.0, 0.0, 172, 34.0],
    [40, 12.0, 0.0, 180, 34.2],
]

# Listas para guardar el registro y pintar la gráfica después
minutos_log = []
temp_core_log = []
fc_log = []
estados_log = []

fc_max_atleta = 195
minuto_anterior = 0

for fila in sesion_csv_simulada:
    min_actual, velocidad, pendiente, fc, t_muneca = fila
    dt_seg = (min_actual - minuto_anterior) * 60

    temp_core = estimador.actualizar(dt_seg, velocidad, pendiente, wbgt_real)
    deriva = detector_deriva.actualizar(dt_seg, velocidad, pendiente, fc, wbgt_real)

    resultado = evaluar_riesgo_termosmart(
        temp_core_estimada=temp_core,
        temp_muneca=t_muneca,
        fc_actual=fc,
        fc_max=fc_max_atleta,
        deriva_cardiovascular=deriva,
        wbgt_ambiental=wbgt_real
    )

    evento, estado_visible, mensaje = histeresis.procesar(resultado)
    estado_actual = estado_visible if estado_visible else "VERDE"

    # Guardar en listas para la gráfica
    minutos_log.append(min_actual)
    temp_core_log.append(temp_core)
    fc_log.append(fc)
    estados_log.append(estado_actual)

    print(f"Min {min_actual:02d} | FC: {fc} lpm | Core: {temp_core}ºC -> Estado: {estado_actual}")
    minuto_anterior = min_actual

# ---------------------------------------------------------------------------
# GENERACIÓN DEL DASHBOARD VISUAL CON MATPLOTLIB
# ---------------------------------------------------------------------------
print("\nGenerando gráfica de rendimiento y estrés térmico...")
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

# Gráfica 1: Temperatura Central Estimada
ax1.plot(minutos_log, temp_core_log, color='crimson', marker='o', linewidth=2, label='Temp. Core Estimada (ºC)')
ax1.axhline(y=38.3, color='orange', linestyle='--', label='Umbral Precaución (38.3ºC)')
ax1.axhline(y=38.8, color='red', linestyle='--', label='Umbral Crítico (38.8ºC)')
ax1.set_ylabel('Temperatura (ºC)', fontsize=12)
ax1.set_title(f'Termosmart Dashboard - Estrés Térmico (WBGT Ambiental: {wbgt_real}ºC)', fontsize=14, fontweight='bold')
ax1.grid(True, linestyle=':', alpha=0.6)
ax1.legend(loc='upper left')

# Gráfica 2: Frecuencia Cardíaca
ax2.plot(minutos_log, fc_log, color='dodgerblue', marker='s', linewidth=2, label='Frecuencia Cardíaca (lpm)')
ax2.axhline(y=fc_max_atleta * 0.8, color='orange', linestyle=':', label='80% FCmax')
ax2.set_xlabel('Tiempo de Sesión (Minutos)', fontsize=12)
ax2.set_ylabel('Frecuencia Cardíaca (lpm)', fontsize=12)
ax2.grid(True, linestyle=':', alpha=0.6)
ax2.legend(loc='upper left')

plt.tight_layout()

# Guardar la imagen automáticamente para usarla luego en tu README
plt.savefig('termosmart_dashboard.png', dpi=300, bbox_inches='tight')
print("Gráfica guardada exitosamente como 'termosmart_dashboard.png'")

plt.show()

