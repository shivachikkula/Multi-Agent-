"""OpenTelemetry tracing setup — 'Azure Monitor' / 'Application Insights'
box. Exports to Azure Monitor when ``APPLICATIONINSIGHTS_CONNECTION_STRING``
is set, otherwise to the console, so distributed traces (gateway ->
orchestrator -> tool calls) are visible either way.
"""
from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from core.config import Settings


def configure_tracing(settings: Settings) -> trace.Tracer:
    provider = TracerProvider(resource=Resource.create({"service.name": settings.otel_service_name}))

    if settings.has_app_insights:
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

            exporter = AzureMonitorTraceExporter(
                connection_string=settings.applicationinsights_connection_string
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except ImportError:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return trace.get_tracer(settings.otel_service_name)


def instrument_fastapi(app) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)
