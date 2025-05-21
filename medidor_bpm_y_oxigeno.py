from machine import Pin, I2C
from ssd1306 import SSD1306_I2C
import time
import max30102
import urequests  # Libreria para hacer solicitudes HTTP
import network
import dht
from umqtt.simple import MQTTClient
import ujson



# instancia para el Max 30102-----------------------
i2c = I2C(0, scl=Pin(22), sda=Pin(21))
sensor = max30102.MAX30102(i2c)
#instancia para la oled -------------------
i3c = I2C(1, scl=Pin(16), sda=Pin(17))
oled = SSD1306_I2C(128, 64, i3c)
oled.fill(0)
oled.show()
#  Pines del RGB (comun cátodo)--------------
# Configuración de pines
PIN_ROJO = 13
PIN_VERDE = 12
PIN_AZUL = 14
rgb = {
    'rojo': Pin(PIN_ROJO, Pin.OUT),
    'verde': Pin(PIN_VERDE, Pin.OUT),
    'azul': Pin(PIN_AZUL, Pin.OUT)
} 
# --- Configuracion de pines y sensores ---
sensorDHT = dht.DHT11(Pin(18))
buzzer = Pin(15, Pin.OUT) 
buzzer.value(0)
# --- Bandera global para señalar el envio del mensaje ---
send_message_flag = False
# --- Funcion que maneja la interrupcion al presionar el boton ---
def button_handler(pin):
    global send_message_flag
    send_message_flag = True
# Configuracion del pin 25 como entrada con resistencia pull-down para el boton
pushA = Pin(25, Pin.IN, Pin.PULL_DOWN)
pushA.irq(trigger=Pin.IRQ_RISING, handler=button_handler)
#----------------------------------------------------------------------
# Configura MQTT
MQTT_BROKER = "Aqui va la IP del servidor mosquitto"
MQTT_PORT = 1883
MQTT_CLIENT_ID = 'esp32-brazalete'
TOPICS = [b"brazalete/edad", b"brazalete/actividad", b"brazalete/oxigeno", b"brazalete/bpm"]
# Variables globales
edad = actividad = oxigeno = bpm = None

# conexion wifi
ssid="Aqui va el nombre de la red"
password="Aqui va la contraseña de la red"
# COnexion de telegram
token = 'Aqui va el token de boot father de telegram'
chat_id = 'Aqui va el ID de telegram'
# Conexion de firebase
FIREBASE_URL = 'Aqui va la url del realtime firebase'
API_KEY = 'Aqui va el api key de realtime firebase'



# Verifica si está presente el sensor ------------------
if not sensor.check_part_id():
    print("MAX30102 no detectado")
    raise SystemExit()
print("Sensor conectado. Iniciando monitoreo...")
# Configuracion
MAX_MUESTRAS = 200
UMBRAL_PICO = 80000
TIEMPO_MIN_ENTRE_PICOS = 400  # en milisegundos


#
# Componentes
# Funcion para leer DHT11
def leer_dht():
    sensorDHT.measure()
    return sensorDHT.temperature(), sensorDHT.humidity()
    
    
# Funcion para activar el buzzer
def activar_buzzer(tiempo=0.5):
    buzzer.value(1)
    time.sleep(tiempo)
    buzzer.value(0)
    time.sleep(0.2)
    
#Mostrar los datos en la pantalla
def mostrar_resultados_oled(bpm, spo2_promedio, temperatura, humedad):
    #Mostrar en OLED
    oled.fill(0)
    oled.text("MAX30102 Monitor", 0, 0)
    oled.text("Temperatura:{}C".format(temperatura), 0, 20)
    oled.text("Humedada:{}%".format(humedad), 0, 30)
    oled.text("BPM: %.1f" % bpm if bpm else "BPM: --", 0, 40)
    oled.text("SpO2: %.1f%%" % spo2_promedio if spo2_promedio else "SpO2: --", 0, 50)
    oled.show()


# Funcion para encender colores
def encender_rgb(color):
    rgb['rojo'].value(color in ["Rojo", "Amarillo"])
    rgb['verde'].value(color in ["Verde", "Amarillo"])
    rgb['azul'].value(0)


#
# Servicios
#

#mandar un mensjae a telegram 
def send_telegram(mensaje):
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    """Envia un mensaje al bot de Telegram."""
    payload = f"chat_id={chat_id}&text={mensaje}"
    try:
        response = urequests.post(url, data=payload, headers=headers)
        print("Codigo de respuesta:", response.status_code)
        print("Contenido:", response.text)
        response.close()
    except Exception as e:
        print("Error al enviar mensaje:", e)
        
        
def connect_wifi():
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print(f"Conectando a la red {ssid}...")
        sta_if.active(True)
        sta_if.connect(ssid, password)
        timeout = 10  # tiempo máximo de espera en segundos
        while not sta_if.isconnected() and timeout > 0:
            print("Esperando conexión...")
            time.sleep(1)
            timeout -= 1
    if sta_if.isconnected():
        print("Conectado con IP:", sta_if.ifconfig()[0])
        return True
    else:
        print("No se pudo conectar en el tiempo esperado.")
        return False
    
    
# Funcion para detectar picos
def detectar_pico(valor):
    return valor > UMBRAL_PICO


# Estimacion de SpO₂
def calcular_spo2(red, ir):
    if ir == 0:
        return 0
    ratio = red / ir
    spo2 = 110 - 25 * ratio
    return max(0, min(spo2, 100))


def monitorear():
    ir_buffer = []
    red_buffer = []
    timestamps = []
    print("📥 Leyendo datos...")
    # Lectura de muestras
    while len(ir_buffer) < MAX_MUESTRAS:
        if sensor.read_sensor():
            ir = sensor.ir
            red = sensor.red
            t = time.ticks_ms()

            ir_buffer.append(ir)
            red_buffer.append(red)
            timestamps.append(t)
        time.sleep(0.05)
    # Deteccion de picos
    picos = []
    for i in range(1, len(ir_buffer) - 1):
        if ir_buffer[i] > ir_buffer[i - 1] and ir_buffer[i] > ir_buffer[i + 1]:
            if detectar_pico(ir_buffer[i]):
                if not picos or (timestamps[i] - picos[-1]) > TIEMPO_MIN_ENTRE_PICOS:
                    picos.append(timestamps[i])
    # Calcular BPM
    if len(picos) > 1:
        intervalos = [picos[i + 1] - picos[i] for i in range(len(picos) - 1)]
        promedio_intervalo = sum(intervalos) / len(intervalos)
        bpm = 60000 / promedio_intervalo
        print("❤️ BPM: %.1f" % bpm)
    else:
        bpm = None
        print("⚠️ No suficientes picos para BPM")

    # Calcular SpO₂
    spo2_values = [calcular_spo2(r, ir) for r, ir in zip(red_buffer, ir_buffer)]
    if spo2_values:
        spo2_promedio = sum(spo2_values) / len(spo2_values)
        print("SpO₂: %.1f%%" % spo2_promedio)
    else:
        spo2_promedio = None
        print("No se pudo calcular SpO₂")
    # Espera antes de reiniciar
    return bpm, spo2_promedio


# Enviar datos a Firebase
def enviar_a_firebase(temperatura, humedad, bpm, oxigeno, resultado_alerta):
    url = FIREBASE_URL + 'lecturas.json?auth=' + API_KEY
    data = {
    "temperatura": temperatura,
    "humedad": humedad,
    "bpm": bpm,
    "oxigeno": oxigeno,
    "alerta": resultado_alerta,  # como lista
    "timestamp": time.time()
    }
    try:
        headers = {'Content-Type': 'application/json'}
        json_data = ujson.dumps(data)  # Serializar a JSON correctamente
        response = urequests.post(url, data=json_data, headers=headers)
        print("Firebase response:", response.text)
        response.close()
    except Exception as e:
        print("Error al enviar a Firebase:", e)


def alerta(edad, actividad, bpm, oxigeno, temperatura, humedad):
    mensaje = []
    peligro = False
    infarto = False
    # --- Evaluar oxigeno ---
    if oxigeno is None:
        mensaje.append("Oxigeno no disponible")
    elif oxigeno >= 84:
        mensaje.append("Oxigenacion normal")
    elif 76 <= oxigeno < 84:
        mensaje.append("Oxigenacion baja leve hipoxemia")
    else:
        mensaje.append("Oxigenacion critica 76 porciento EN PELIGRO")
        peligro = True
    # --- Evaluar BPM segun actividad ---
    if bpm is None:
        mensaje.append("BPM no disponible")
    else:
        if actividad == "reposo":
            if bpm < 50: 
                mensaje.append("Peligro ritmo cardiaco bajo")
                peligro = True
            elif bpm < 60:
                mensaje.append("Ritmo cardiaco bajo en reposo (posible bradicardia)")
            elif bpm > 130:
                mensaje.append("Peligro ritmo cardiaco muy alto")
                peligro = True
                infarto = True
            elif bpm > 115:
                mensaje.append("Peligro ritmo elevado")
                peligro = True
            else:
                mensaje.append("ritmo cardiaco adecuado en reposo")

        elif actividad == "cansada":
            if bpm < 80:
                mensaje.append("Peligro ritmo cardiaco muy bajo")
                peligro = True
            elif bpm < 90:
                mensaje.append("Ritmo cardiaco bajo para actividad cansada")
            elif bpm > 150:
                mensaje.append("cardiaco muy alto POSIBLE ATAQUE CARDiACO")
                peligro = True
                infarto = True
            elif bpm > 130:
                mensaje.append("Peligro ritmo caridaco muy alto")
                peligro = True
            else:
                mensaje.append("Ritmo cardiaco adecuado para actividad cansada")

        elif actividad == "exhaustiva":
            if bpm < 90:
                mensaje.append("PELIGRO")
                peligro = True
            elif bpm < 100:
                mensaje.append("Ritmo cardiaco bajo para actividad exhaustiva")
            elif bpm > 180:
                mensaje.append("Peligro")
                peligro = True
                infarto = True
            elif bpm > 160:
                mensaje.append("Ritmo cardiaco muy alto para actividad exhaustiva")
                peligro = True
            else:
                mensaje.append("Ritmo cardiaco adecuado para actividad exhaustiva")
        elif actividad == "muy exhaustiva":
            if bpm < 100:
                mensaje.append("Peligro ritmo cardiaco muy bajo")
                peligro = True
            elif bpm < 110:
                mensaje.append("Ritmo cardiaco bajo para actividad intensa")
            elif bpm > 270:
                mensaje.append("Peligro ritmo cardiaco muy alto ")
                peligro = True
                infarto = True
            elif bpm > 200:
                mensaje.append("Ritmo cardiaco muy alto fuera del rango saludable POSIBLE PELIGRO")
                peligro = True
            else:
                mensaje.append("Ritmo cardiaco adecuado del rango para atletas")
        else:
            mensaje.append("Actividad no reconocida")

# --- Evaluar clima como factor de riesgo ---
    if temperatura is not None and humedad is not None:
        if temperatura >= 32 and humedad >= 70:
            mensaje.append("Clima caluroso y humedo: puede elevar el ritmo cardiaco")
        elif temperatura <= 15 and humedad >= 70:
            mensaje.append("Clima frio y humedo: puede aumentar la presion arterial")
    return " ".join(mensaje)

# Funcion a ejecutar cuando se reciben todos los datos
def monitorearPrueba(edad, actividad, bpm, oxigeno):
    print('--- DATOS COMPLETOS ---')
    print('Edad:', edad)
    print('Actividad:', actividad)
    print('BPM:', bpm)
    print('Oxigeno:', oxigeno)
    temperatura, humedad = leer_dht()
    if bpm is None and oxigeno is None:
        bpm, oxigeno = monitorear()
    mostrar_resultados_oled(bpm,oxigeno,temperatura,humedad)
    resultado_alerta = alerta(int(edad), str(actividad), int(bpm), int(oxigeno), temperatura, humedad)
    print("Resultado de alerta:", resultado_alerta)
    enviar_a_firebase(temperatura, humedad, bpm, oxigeno, resultado_alerta)
    if "Ritmo cardiaco bajo".lower() in resultado_alerta.lower():
        encender_rgb("Amarillo")
    elif "Ritmo cardiaco muy alto".lower() in resultado_alerta.lower():
        encender_rgb("Rojo")
    elif "Ritmo cardiaco adecuado".lower() in resultado_alerta.lower():
        encender_rgb("Verde")
    elif "Peligro".lower() in resultado_alerta.lower():
        send_telegram(resultado_alerta)
        activar_buzzer()
        encender_rgb("Rojo")
    else:
        pass
    time.sleep(3)
        


# Callback para mensajes MQTT
def manejar_mensaje(topic, msg):
    global edad, actividad, oxigeno, bpm
    topic = topic.decode()
    msg = msg.decode()
    print('Mensaje recibido en', topic, ':', msg)
    if topic == 'brazalete/edad':
        edad = int(msg)
    elif topic == 'brazalete/actividad':
        actividad = msg
    elif topic == 'brazalete/oxigeno':
        oxigeno = int(msg)
    elif topic == 'brazalete/bpm':
        bpm = int(msg)

# Conectarse al broker MQTT y suscribirse a topicos
def suscripciones():
    global client
    print('Conectando al broker MQTT...')
    client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER, port=MQTT_PORT)
    client.set_callback(manejar_mensaje)
    client.connect()
    print('Conectado a MQTT broker')
    for topic in TOPICS:
        client.subscribe(topic)
        print('Suscrito a', topic.decode())


# Funcion principal
def main():
    global send_message_flag
    connect_wifi()
    suscripciones()
    try:
        while True:
            if send_message_flag:
                print("¡Boton presionado! Enviando mensaje a Telegram...")
                send_telegram("Alerta de paro cardiaco")
                send_message_flag = False
            time.sleep(1)
            client.check_msg()
            if edad is not None and actividad is not None:
                monitorearPrueba(edad, actividad, bpm, oxigeno)
            time.sleep(1)
    except KeyboardInterrupt:
        print('Desconectando...')
        client.disconnect()
# Ejecutar
main()

