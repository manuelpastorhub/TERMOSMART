!pip install requests
"""
Termosmart - Motor de estimación de estrés térmico y decisión de riesgo
para wearables en deportistas de resistencia (Con Simulación CSV y Gráfica Matplotlib).

IMPORTANTE (uso previsto):
Este módulo es un sistema de APOYO A LA DECISIÓN, no un dispositivo de
diagnóstico médico. La temperatura cutánea de muñeca es un proxy indirecto
de la temperatura central (core).
"""

import math
import requests
from collections import deque
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# 1. INTEGRACIÓN API EXTERNA (OPEN-METEO)
# ---------------------------------------------------------------------------
class ProveedorMeteo:
    """
    Se conecta a la API gratuita de Open-Meteo para extraer la temperatura,
    humedad, viento, radiación y elevación reales según las coordenadas GPS.
    """
    def __init__(self, latitud: float, longitud: float):
        self.latitud = latitud
        self.longitud = longitud
        self.url_clima = f"https://api.open-meteo.com/v1/forecast?latitude={self.latitud}&longitude={self.longitud}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation"
        self.url_elevacion = f"https://api.open-meteo.com/v1/elevation?latitude={self.latitud}&longitude={self.longitud}"

    def obtener_datos_entorno(self):
        """Devuelve (temp_aire, humedad, viento, radiacion, altitud)."""
        try:
            resp_clima = requests.get(self.url_clima, timeout=5)
            resp_clima.raise_for_status()
            datos_clima = resp_clima.json()['current']

            temp_aire = datos_clima['temperature_2m']
            humedad = datos_clima['relative_humidity_2m']
            viento = datos_clima['wind_speed_10m'] / 3.6  # km/h a m/s
            radiacion = datos_clima['shortwave_radiation']

            resp_elev = requests.get(self.url_elevacion, timeout=5)
            resp_elev.raise_for_status()
            altitud = resp_elev.json()['elevation'][0]

            return temp_aire, humedad, viento, radiacion, altitud

        except requests.exceptions.RequestException as e:
            print(f"Error conectando a la API: {e}. Usando valores de fallback.")
            return 25.0, 50.0, 0.0, 0.0, 0.0

# ---------------------------------------------------------------------------
# 2. CÁLCULOS FÍSICOS Y MECÁNICOS
# ---------------------------------------------------------------------------
def _presion_vapor_saturacion_hpa(temp_aire_c: float) -> float:
    return 6.105 * math.exp((17.27 * temp_aire_c) / (237.7 + temp_aire_c))

def calcular_wbgt_estandar(temp_aire: float, humedad: float, radiacion_solar: float = 0.0, velocidad_viento: float = 0.0) -> float:
    if not (0.0 <= humedad <= 100.0):
        raise ValueError(f"Humedad fuera de rango físico: {humedad}")

    e = (humedad / 100.0) * _presion_vapor_saturacion_hpa(temp_aire)
    termico_base = temp_aire * 0.567 + e * 0.393 + 3.94
    factor_radiacion = radiacion_solar * 0.008
    factor_viento = velocidad_viento * 0.6

    return round(termico_base + factor_radiacion - factor_viento, 2)

def _produccion_calor_metabolico_watts(velocidad_kmh: float, pendiente_pct: float, peso_kg: float) -> float:
    velocidad_m_min = velocidad_kmh * 1000.0 / 60.0
    vo2_ml_kg_min = 0.2 * velocidad_m_min + 0.9 * velocidad_m_min * (pendiente_pct / 100.0) + 3.5
    vo2_l_min = vo2_ml_kg_min * peso_kg / 1000.0
    potencia_metabolica_w = vo2_l_min * 20.9 * 1000.0 / 60.0
    eficiencia_mecanica = 0.20
    return potencia_metabolica_w * (1 - eficiencia_mecanica)

class EstimadorTemperaturaCentral:
    CALOR_ESPECIFICO_CUERPO_J_KG_C = 3470.0
    CONSTANTE_DISIPACION_W_POR_C = 700.0

    def __init__(self, peso_kg: float, temp_core_inicial: float = 37.0):
        if peso_kg <= 0:
            raise ValueError("peso_kg debe ser mayor que 0.")
        self.peso_kg = peso_kg
        self.temp_core = temp_core_inicial

    def actualizar(self, dt_seg: float, velocidad_kmh: float, pendiente_pct: float, wbgt_ambiental: float) -> float:
        if dt_seg <= 0:
            raise ValueError("dt_seg debe ser mayor que 0.")

        calor_metabolico_w = _produccion_calor_metabolico_watts(velocidad_kmh, pendiente_pct, self.peso_kg)
        capacidad_ambiental = max(0.0, 35.0 - wbgt_ambiental) / 35.0
        exceso_termico_c = max(0.0, self.temp_core - 37.0)
        respuesta_termorreguladora = min(1.0, exceso_termico_c / 2.0)

        disipacion_w = self.CONSTANTE_DISIPACION_W_POR_C * capacidad_ambiental * respuesta_termorreguladora
        balance_w = calor_metabolico_w - disipacion_w
        capacidad_calorifica_j_c = self.CALOR_ESPECIFICO_CUERPO_J_KG_C * self.peso_kg
        delta_c = (balance_w * dt_seg) / capacidad_calorifica_j_c

        self.temp_core += delta_c
        return round(self.temp_core, 3)

# ---------------------------------------------------------------------------
# 3. DETECCIÓN DE DERIVA Y MOTOR DE RIESGO
# ---------------------------------------------------------------------------
class DetectorDerivaCardiovascular:
    def __init__(self, ventana_seg: float = 300.0, tolerancia_velocidad_kmh: float = 0.5, tolerancia_pendiente_pct: float = 0.5, descarte_inicial_seg: float = 90.0, umbral_pendiente_fc_bpm_min: float = 0.3, wbgt_umbral: float = 27.0):
        self.ventana_seg = ventana_seg
        self.tolerancia_velocidad = tolerancia_velocidad_kmh
        self.tolerancia_pendiente = tolerancia_pendiente_pct
        self.descarte_inicial_seg = descarte_inicial_seg
        self.umbral_pendiente_fc = umbral_pendiente_fc_bpm_min
        self.wbgt_umbral = wbgt_umbral
        self._buffer = deque()
        self._t = 0.0

    def actualizar(self, dt_seg: float, velocidad_kmh: float, pendiente_pct: float, fc_actual: float, wbgt_ambiental: float) -> bool:
        if dt_seg <= 0:
            raise ValueError("dt_seg debe ser mayor que 0.")

        self._t += dt_seg
        self._buffer.append((self._t, velocidad_kmh, pendiente_pct, fc_actual))
        while self._buffer and self._t - self._buffer[0][0] > self.ventana_seg:
            self._buffer.popleft()

        if self._t < self.ventana_seg:
            return False

        velocidades = [s[1] for s in self._buffer]
        pendientes = [s[2] for s in self._buffer]

        if (max(velocidades) - min(velocidades)) > self.tolerancia_velocidad:
            return False
        if (max(pendientes) - min(pendientes)) > self.tolerancia_pendiente:
            return False

        t0 = self._buffer[0][0]
        muestras = [s for s in self._buffer if (s[0] - t0) >= self.descarte_inicial_seg]
        if len(muestras) < 3:
            return False

        ts = [s[0] for s in muestras]
        fcs = [s[3] for s in muestras]
        n = len(ts)
        t_media = sum(ts) / n
        fc_media = sum(fcs) / n
        numerador = sum((t - t_media) * (fc - fc_media) for t, fc in zip(ts, fcs))
        denominador = sum((t - t_media) ** 2 for t in ts)

        if denominador == 0:
            return False

        pendiente_fc_bpm_min = (numerador / denominador) * 60.0
        return (pendiente_fc_bpm_min >= self.umbral_pendiente_fc and wbgt_ambiental >= self.wbgt_umbral)

def evaluar_riesgo_termosmart(temp_core_estimada: float, temp_muneca: float, fc_actual: float, fc_max: float, deriva_cardiovascular: bool, wbgt_ambiental: float) -> str:
    if fc_max <= 0:
        raise ValueError("fc_max debe ser mayor que 0.")
    if fc_actual < 0:
        raise ValueError("fc_actual no puede ser negativa.")

    porcentaje_fc = (fc_actual / fc_max) * 100

    if (temp_core_estimada >= 39.3) or (temp_core_estimada >= 38.8 and wbgt_ambiental >= 30.0 and deriva_cardiovascular and temp_muneca >= 33.8):
        return "ROJO: ¡ALERTA CRÍTICA! Temperatura central estimada en rango peligroso, con deriva cardiovascular sostenida y confirmación periférica. Cese inmediato de la actividad."
    elif wbgt_ambiental >= 27.0 and (porcentaje_fc >= 80 or temp_core_estimada >= 38.3 or deriva_cardiovascular):
        return "AMARILLO: Precaución. Temperatura central estimada y/o respuesta cardiovascular muestran fatiga térmica inicial. Reducir intensidad."
    else:
        return "VERDE: Homeostasis conservada. Parámetros ambientales y biométricos dentro de márgenes seguros."

class HisteresisAlerta:
    _ORDEN_NIVELES = {"VERDE": 0, "AMARILLO": 1, "ROJO": 2}

    def __init__(self, lecturas_para_escalar: int = 2, lecturas_para_desescalar: int = 4):
        self.lecturas_para_escalar = lecturas_para_escalar
        self.lecturas_para_desescalar = lecturas_para_desescalar
        self.estado = "NORMAL"
        self._nivel_candidato = None
        self._contador_candidato = 0

    def procesar(self, resultado_bruto: str):
        nivel_bruto = resultado_bruto.split(":", 1)[0]
        nivel_actual_equivalente = self.estado if self.estado != "NORMAL" else "VERDE"

        if nivel_bruto == nivel_actual_equivalente:
            self._nivel_candidato = None
            self._contador_candidato = 0
            return None, (self.estado if self.estado != "NORMAL" else None), None

        if nivel_bruto != self._nivel_candidato:
            self._nivel_candidato = nivel_bruto
            self._contador_candidato = 1
        else:
            self._contador_candidato += 1

        escalando = self._ORDEN_NIVELES[nivel_bruto] > self._ORDEN_NIVELES[nivel_actual_equivalente]
        umbral_confirmacion = self.lecturas_para_escalar if escalando else self.lecturas_para_desescalar

        if self._contador_candidato >= umbral_confirmacion:
            self._nivel_candidato = None
            self._contador_candidato = 0
            if nivel_bruto == "VERDE":
                self.estado = "NORMAL"
                return "VUELVE_A_NORMALIDAD", None, "Parámetros seguros restablecidos."
            else:
                self.estado = nivel_bruto
                return f"ENTRA_{nivel_bruto}", self.estado, resultado_bruto

        return None, (self.estado if self.estado != "NORMAL" else None), None

# ---------------------------------------------------------------------------
# BLOQUE DE EJECUCIÓN (SIMULADOR CSV + MATPLOTLIB)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
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
    plt.show()
