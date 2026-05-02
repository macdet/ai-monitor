def monitor_system() -> dict[str, Any]:
    global _last_thermal_state

    payload: dict[str, Any] = {
        "ollama": None,
        "docker": None,
        "gpu": None,
        "thermal": None,
        "actions": {
            "model_unloaded": False,
            "unloaded_model": None,
        },
    }

    # 1. Ollama Check
    models = get_loaded_models()
    payload["ollama"] = {
        "models": [
            {
                "name": m.name,
                "processor": m.processor,
                "size_gb": m.size_gb,
                "vram_used_gb": m.vram_gb,
                "context": m.context,
            }
            for m in models
        ],
    }

    # 2. Docker Check
    try:
        docker_stats = get_docker_stats()
        payload["docker"] = docker_stats
    except Exception as exc:
        logger.exception("Docker Check fehlgeschlagen")

    # 3. GPU + Thermal Check
    try:
        gpu = get_gpu_stats()
        payload["gpu"] = gpu

        # Thermal Decision
        thermal_values = [
            value
            for value in (
                gpu.temperature_hotspot,
                gpu.temperature_mem,
                gpu.temperature_edge,
            )
            if value is not None
        ]
        thermal_temp_c = max(thermal_values) if thermal_values else None

        thermal_decision = thermal_policy.evaluate(
            temperature_c=thermal_temp_c,
            temps_raw=GpuTemps(
                edge=gpu.temperature_edge,
                hotspot=gpu.temperature_hotspot,
                mem=gpu.temperature_mem,
            ),
        )

        payload["thermal"] = {
            "state": thermal_decision.state,
            "temperature_c": thermal_decision.temperature_c,
            "reason": thermal_decision.reason,
        }

        # Thermal-Alert nur bei Zustandswechsel (kein Spam)
        if thermal_decision.state != _last_thermal_state:
            logger.info(
                "Thermal state: %s → %s",
                _last_thermal_state,
                thermal_decision.state,
            )
            _last_thermal_state = thermal_decision.state

    except Exception as exc:
        logger.exception("GPU/Thermal Check fehlgeschlagen")

    # 4. Alert Policy Evaluation
    # SystemState für AlertPolicy erstellen
    system_state = SystemState(
        gpu=gpu,
        ollama_models=models,
        ollama_hanging=payload.get("ollama", {}).get("status") == "error",
        docker_containers=payload.get("docker", []),
    )

    alerts = alert_policy.evaluate(system_state)

    # 5. Action Policy Evaluation
    recent_restart_count = 0  # TODO: Historisierung implementieren
    actions = action_policy.evaluate(
        system_state,
        thermal_decision,
        alerts,
        recent_restart_count,
    )

    # 6. Actions ausführen
    for action in actions:
        if isinstance(action, UnloadModel):
            ok, model = unload_current_ollama_model(ollama_url=OLLAMA_URL)
            payload["actions"]["model_unloaded"] = ok
            payload["actions"]["unloaded_model"] = model

            if ok and model:
                logger.info(f"Modell entladen: {model}")
            else:
                logger.error("Modell konnte nicht entladen werden")

        elif isinstance(action, RestartContainer):
            logger.info(f"Würde Container neu starten: {action.reason}")
            # TODO: Container restart logic

        elif isinstance(action, SendAlert):
            success = send_ntfy_alerts([action.reason])
            if success:
                logger.info(f"Alert gesendet: {action.reason}")
            else:
                logger.error(f"Alert konnte nicht gesendet werden: {action.reason}")

        elif isinstance(action, NoOp):
            logger.debug(action.reason)

    return payload


def run_monitor_loop() -> None:
    logger.info("ai-monitor gestartet, Intervall=%ss", POLL_INTERVAL_SECONDS)

    while True:
        try:
            payload = monitor_system()
            logger.info("Monitor payload: %s", payload)
        except Exception:
            logger.exception("Fehler im Monitor-Loop")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_monitor_loop()
