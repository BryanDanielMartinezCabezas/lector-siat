// Definición de pines para los LEDs de la cajita
#define LED_ROJO      2
#define LED_VERDE     3
#define LED_AMARILLO1 4
#define LED_AMARILLO2 5

void setup() {
  // Configurar todos los pines como SALIDA
  pinMode(LED_ROJO, OUTPUT);
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARILLO1, OUTPUT);
  pinMode(LED_AMARILLO2, OUTPUT);
  
  // Los dos LEDs amarillos deben estar siempre encendidos (iluminación / encendido)
  digitalWrite(LED_AMARILLO1, HIGH);
  digitalWrite(LED_AMARILLO2, HIGH);
  
  // Estado inicial: LEDs de resultado apagados
  digitalWrite(LED_ROJO, LOW);
  digitalWrite(LED_VERDE, LOW);
  
  // Iniciar comunicación serial a 115200 baudios (coincide con la config del software)
  Serial.begin(115200);
  Serial.println("=== CAJITA LED INICIADA ===");
  Serial.println("Amarillos: ON | Rojo/Verde: Esperando comando...");
}

void loop() {
  // Escuchar comandos del puerto serial enviados por el script de Python
  if (Serial.available() > 0) {
    char comando = Serial.read();
    
    // Comando 'V' o 'G' -> Lectura exitosa (Verde)
    if (comando == 'V' || comando == 'v' || comando == 'G' || comando == 'g') {
      digitalWrite(LED_VERDE, HIGH);
      digitalWrite(LED_ROJO, LOW);
      Serial.println("🟢 LED verde encendido (Lectura correcta)");
    }
    // Comando 'R' -> Lectura fallida / Revisión requerida (Rojo)
    else if (comando == 'R' || comando == 'r') {
      digitalWrite(LED_VERDE, LOW);
      digitalWrite(LED_ROJO, HIGH);
      Serial.println("🔴 LED rojo encendido (Error/Revisión)");
    }
    // Comando 'O' o 'A' -> Apagar ambos (estado de espera / reset)
    else if (comando == 'O' || comando == 'o' || comando == 'A' || comando == 'a') {
      digitalWrite(LED_VERDE, LOW);
      digitalWrite(LED_ROJO, LOW);
      Serial.println("⚪ LEDs de estado apagados");
    }
  }
}
