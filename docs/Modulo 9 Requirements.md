9. Monitoreo de Pacientes
   Simula el procesamiento de datos provenientes de dispositivos médicos.
   Ingesta de Telemetría: Simulación de recepción de datos de sensores (frecuencia cardíaca, SpO2,
   etc.) mediante colas de mensajes.
   Motor de Reglas: Evaluación en tiempo real de los datos recibidos (ej: si HR > 120 por 2 minutos,
   generar alerta).
   Panel de Monitoreo: Dashboard para enfermería con el estado de los pacientes.
   Alertas de Emergencia: Envío de evento de alta prioridad al Módulo de Internación ante un
   código rojo detectado por sensores.
