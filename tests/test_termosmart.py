import unittest
import sys

# Añadimos la ruta para que los tests encuentren la librería en la carpeta 'src'
sys.path.append('../src')

from termosmart import (
    calcular_wbgt_estandar,
    EstimadorTemperaturaCentral,
    evaluar_riesgo_termosmart,
    HisteresisAlerta
)

class TestTermosmart(unittest.TestCase):

    def test_calcular_wbgt_limites_humedad(self):
        """Verifica que el sistema rechace valores de humedad físicamente imposibles."""
        with self.assertRaises(ValueError):
            calcular_wbgt_estandar(temp_aire=25.0, humedad=150.0)
        with self.assertRaises(ValueError):
            calcular_wbgt_estandar(temp_aire=25.0, humedad=-10.0)

    def test_estimador_temperatura_inicializacion(self):
        """Verifica que no se puedan introducir pesos corporales negativos."""
        with self.assertRaises(ValueError):
            EstimadorTemperaturaCentral(peso_kg=-5)

    def test_estimador_temperatura_incremento(self):
        """Verifica que la temperatura corporal suba al aplicar carga metabólica."""
        estimador = EstimadorTemperaturaCentral(peso_kg=75, temp_core_inicial=37.0)
        # Simulamos 10 minutos (600 seg) corriendo a 12 km/h
        nueva_temp = estimador.actualizar(dt_seg=600, velocidad_kmh=12.0, pendiente_pct=0.0, wbgt_ambiental=25.0)
        
        self.assertGreater(nueva_temp, 37.0, "La temperatura debe aumentar durante el ejercicio.")
        self.assertLess(nueva_temp, 40.0, "El incremento en 10 min no debe ser irreal.")

    def test_evaluar_riesgo_salud_verde(self):
        """Verifica que el motor devuelva VERDE en condiciones seguras de salud."""
        riesgo = evaluar_riesgo_termosmart(
            temp_core_estimada=37.5,
            temp_muneca=32.0,
            fc_actual=130,
            fc_max=195,
            deriva_cardiovascular=False,
            wbgt_ambiental=25.0
        )
        self.assertTrue(riesgo.startswith("VERDE"), "Debería mantener homeostasis segura.")

    def test_evaluar_riesgo_salud_rojo(self):
        """Verifica que el motor dispare ALERTA CRÍTICA al superar umbrales de golpe de calor."""
        riesgo = evaluar_riesgo_termosmart(
            temp_core_estimada=39.5, # Temperatura crítica de riesgo de salud
            temp_muneca=34.0,
            fc_actual=185,
            fc_max=195,
            deriva_cardiovascular=True,
            wbgt_ambiental=32.0
        )
        self.assertTrue(riesgo.startswith("ROJO"), "Debería proteger al usuario y pedir cese inmediato.")

    def test_histeresis_filtro_ruido(self):
        """Verifica que el sistema exija confirmaciones antes de lanzar una alerta para evitar falsos positivos."""
        filtro = HisteresisAlerta(lecturas_para_escalar=2)
        
        # Primera lectura de peligro (el filtro debería bloquearla por si es un error del sensor)
        evento, estado, _ = filtro.procesar("ROJO: Alerta Crítica")
        self.assertIsNone(evento, "No debe disparar alerta a la primera lectura.")
        
        # Segunda lectura de peligro (confirmación)
        evento, estado, _ = filtro.procesar("ROJO: Alerta Crítica")
        self.assertEqual(estado, "ROJO", "Debe confirmar el riesgo a la segunda lectura consecutiva.")

if __name__ == '__main__':
    unittest.main(verbosity=2)
