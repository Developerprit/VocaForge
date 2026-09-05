"""OpenAPI 3.0 document for the VocaForge Architecture REST API (/api/v1).

Kept as plain data so it can be served verbatim and used to generate clients.
"""
from __future__ import annotations

from typing import Any, Dict


def openapi_doc() -> Dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "VocaForge Architecture API",
            "version": "1.0.0",
            "description": (
                "Versioned REST surface of VocaForge (a pure-Python DiffSinger "
                "framework). Lets external projects and websites integrate singing "
                "voice synthesis. Two extension points: Backend (synthesis engine) "
                "and ModelLoader (model storage resolver)."
            ),
            "license": {"name": "Available License", "url": "https://license.kscm.top/available.md"},
        },
        "servers": [{"url": "http://127.0.0.1:8080", "description": "default local gateway"}],
        "paths": {
            "/api/v1/health": {
                "get": {
                    "summary": "Liveness + capabilities",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "status": "ok",
                                        "version": "0.2.0",
                                        "backends": ["stub", "diffsinger"],
                                        "loaders": ["local"],
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/v1/version": {
                "get": {
                    "summary": "Framework version",
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/api/v1/models": {
                "get": {
                    "summary": "List registered voice libraries",
                    "responses": {"200": {"description": "ok"}},
                },
                "post": {
                    "summary": "Register a voice library (active integration)",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ModelSpec"},
                                "example": {
                                    "id": "my-voice",
                                    "name": "My Voice",
                                    "type": "synthesizer",
                                    "path": "/models/my-voice",
                                    "lang": "zh",
                                    "backend": "stub",
                                },
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "created"},
                        "400": {"description": "invalid spec"},
                    },
                },
            },
            "/api/v1/models/{id}": {
                "get": {
                    "summary": "Get one library spec",
                    "parameters": [
                        {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {
                        "200": {"description": "ok"},
                        "404": {"description": "not found"},
                    },
                }
            },
            "/api/v1/resolve": {
                "post": {
                    "summary": "Resolve a model id/name to its spec",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"type": "object", "properties": {"model": {"type": "string"}}}
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "resolved"},
                        "404": {"description": "not found"},
                    },
                }
            },
            "/api/v1/synth": {
                "post": {
                    "summary": "Synthesize audio",
                    "description": (
                        "Returns raw audio/wav when `format=wav` (query or body) or "
                        "Accept: audio/wav. Otherwise returns JSON with audio_base64."
                    ),
                    "parameters": [
                        {
                            "name": "format",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "enum": ["json", "wav"]},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "model": {"type": "string"},
                                        "lyrics": {"type": "string"},
                                        "midi": {"type": "integer"},
                                        "duration": {"type": "number"},
                                        "project": {"type": "object"},
                                        "out": {"type": "string"},
                                    },
                                },
                                "example": {"model": "stub-zh", "lyrics": "你好世界", "duration": 0.35},
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "synthesis result",
                            "content": {
                                "audio/wav": {"schema": {"type": "string", "format": "binary"}},
                                "application/json": {
                                    "example": {
                                        "ok": True,
                                        "sample_rate": 44100,
                                        "bytes": 401328,
                                        "audio_base64": "<base64>",
                                    }
                                },
                            },
                        },
                        "404": {"description": "model not found"},
                        "500": {"description": "synthesis error"},
                    },
                }
            },
            "/api/v1/openapi.json": {
                "get": {"summary": "This OpenAPI document", "responses": {"200": {"description": "ok"}}}
            },
        },
        "components": {
            "schemas": {
                "ModelSpec": {
                    "type": "object",
                    "required": ["id", "name", "type", "path"],
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "type": {"type": "string", "enum": ["diffusion", "synthesizer", "vocoder"]},
                        "path": {"type": "string"},
                        "sample_rate": {"type": "integer"},
                        "lang": {"type": "string"},
                        "backend": {"type": "string"},
                        "extra": {"type": "object"},
                    },
                }
            }
        },
    }
