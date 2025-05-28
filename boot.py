# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()
# This file is executed on every boot (including wake-boot from deepsleep)
"""
Este programa implementa un sistema de captura y almacenamiento remoto de imágenes
utilizando un módulo ESP32-CAM, diseñado para aplicaciones IoT en el área de telemedicina y monitoreo remoto.
El código realiza las siguientes funciones clave:

-  Conexión WiFi
-  Captura de imágenes
-  Almacenamiento en Google Drive

Autores:
    Saulo Blas Silva Brandi (Integración hardware/software)
    Avila Cano Rafael (Desarrollo de Apps Script y API)
    Angel Gerardo Mendoza Granados (Optimización de imagen y WiFi)

Fecha: 20 de mayo de 2025
Práctica: Sistema de Captura Médica con ESP32-CAM y Google Drive
"""

import urequests
import ubinascii
import time
import camera
from machine import Pin
import network
import time

# conexion wifi
ssid="Aqui va el nombre de la red"
password="Aqui va la contraseña de la red"
SCRIPT_URL = "Aqui se pone el link de la carpeta drive"
led_flash = Pin(4, Pin.OUT)

def iniciar_camara():
    camera.init(0, format=camera.JPEG)
    camera.framesize(camera.FRAME_SVGA)
    camera.quality(10)
    camera.brightness(2)
    camera.contrast(2)
    camera.saturation(1)
    camera.whitebalance(camera.WB_SUNNY)
    camera.speffect(camera.EFFECT_NONE)
    print("Cámara configurada")

def capturar_y_subir():
    iniciar_camara()
    try:
        print("Encendiendo flash")
        led_flash.value(1)
        time.sleep(1)
        
        print("Capturando foto...")
        foto = camera.capture()
        if not foto or len(foto) < 1024:
            print("Foto inválida")
            return
        print(f"Foto capturada ({len(foto)/1024:.1f} KB)")
        
        imagen_b64 = ubinascii.b2a_base64(foto).decode().strip()
        
        # Construir payload form-urlencoded
        # Manual URL encoding, reemplazamos +, /, = con %XX
        def urlencode(s):
            import ure
            # Simple replace for base64 safe chars
            s = s.replace('+', '%2B')
            s = s.replace('/', '%2F')
            s = s.replace('=', '%3D')
            return s
        
        body = 'data=' + urlencode(imagen_b64) + '&mimetype=image/jpeg'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        print("Subiendo a Drive...")
        r = urequests.post(SCRIPT_URL, data=body, headers=headers)
        print("Respuesta:", r.text)
        r.close()
    finally:
        led_flash.value(0)
        camera.deinit()
        print("Recursos liberados")

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
    
    
connect_wifi()
capturar_y_subir()
print("Proceso completado!") 