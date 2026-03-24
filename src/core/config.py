import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from current directory first, then package root as fallback
load_dotenv(Path.cwd() / ".env")
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# Paths
PACKAGE_ROOT = Path(__file__).resolve().parent.parent  # Points to src/

# Working directory paths (output goes where the user runs the command)
CWD = Path.cwd()
PROJECTS_DIR = CWD / "projects"
OUTPUT_DIR = CWD / "output"

# API
PROVIDER = os.getenv("PROVIDER", "anthropic")  # "anthropic", "openrouter", or "local"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434")
MODEL = os.getenv("MODEL", "claude-sonnet-4-6")
DEFAULT_MODE = os.getenv("DEFAULT_MODE", "capella")  # "capella" or "rhapsody"

# Per-workflow model overrides
DECOMPOSE_MODEL = os.getenv("DECOMPOSE_MODEL", "claude-sonnet-4-6")
MBSE_MODEL = os.getenv("MBSE_MODEL", "claude-sonnet-4-6")

# Decomposition defaults
DEFAULT_MAX_DEPTH = 4
DEFAULT_MAX_BREADTH = 3

# Level names for requirements decomposition
LEVEL_NAMES = {
    1: "Whole Ship",
    2: "Major System",
    3: "Subsystem",
    4: "Equipment",
}

# Pricing (USD per million tokens) — used as fallback when API doesn't return actual cost
MODEL_PRICING = {
    # Anthropic direct
    "claude-sonnet-4-6": {"input_per_mtok": 3.00, "output_per_mtok": 15.00},
    "claude-opus-4-6": {"input_per_mtok": 15.00, "output_per_mtok": 75.00},
    "claude-haiku-4-5": {"input_per_mtok": 0.80, "output_per_mtok": 4.00},
    # OpenRouter models
    "anthropic/claude-sonnet-4": {"input_per_mtok": 3.00, "output_per_mtok": 15.00},
    "anthropic/claude-haiku-4.5": {"input_per_mtok": 0.80, "output_per_mtok": 4.00},
    "google/gemini-2.5-flash": {"input_per_mtok": 0.15, "output_per_mtok": 0.60},
    "google/gemini-2.5-pro": {"input_per_mtok": 1.25, "output_per_mtok": 10.00},
    "deepseek/deepseek-chat-v3-0324": {"input_per_mtok": 0.27, "output_per_mtok": 1.10},
    "deepseek/deepseek-r1": {"input_per_mtok": 0.55, "output_per_mtok": 2.19},
    "openai/gpt-4o-mini": {"input_per_mtok": 0.15, "output_per_mtok": 0.60},
    "openai/gpt-4o": {"input_per_mtok": 2.50, "output_per_mtok": 10.00},
    "meta-llama/llama-4-maverick": {"input_per_mtok": 0.20, "output_per_mtok": 0.60},
    "qwen/qwen3-235b-a22b": {"input_per_mtok": 0.20, "output_per_mtok": 0.60},
    "qwen/qwen3-32b": {"input_per_mtok": 0.10, "output_per_mtok": 0.30},
    "qwen/qwen3-30b-a3b": {"input_per_mtok": 0.05, "output_per_mtok": 0.15},
}

# Model catalogue with descriptions for UI (MBSE descriptions, cost_per_run key)
MODEL_CATALOGUE = [
    {
        "id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "provider": "anthropic",
        "price": "$3 / $15 per Mtok", "cost_per_run": "~$0.20-0.40",
        "quality": "excellent", "speed": "medium",
        "description": "Best quality for MBSE model generation. Strong at structured reasoning, Capella/Rhapsody schema compliance, and systems engineering domain knowledge. Recommended for production use.",
        "pros": ["Best MBSE model generation quality", "Strongest engineering reasoning", "Excellent structured output"],
        "cons": ["Higher cost", "Slower than budget options"],
    },
    {
        "id": "claude-haiku-4-5", "name": "Claude Haiku 4.5", "provider": "anthropic",
        "price": "$0.80 / $4 per Mtok", "cost_per_run": "~$0.05-0.10",
        "quality": "good", "speed": "fast",
        "description": "Fast and cheap with good quality. Great for testing prompts, iterating on settings, or budget-conscious MBSE model generation runs.",
        "pros": ["4x cheaper than Sonnet", "Fast responses", "Good quality for the price"],
        "cons": ["Shallower reasoning", "May miss nuanced MBSE modelling details"],
    },
    {
        "id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet 4 (OpenRouter)", "provider": "openrouter",
        "price": "$3 / $15 per Mtok", "cost_per_run": "~$0.20-0.40",
        "quality": "excellent", "speed": "medium",
        "description": "Same Claude Sonnet quality routed through OpenRouter. Use if you have OpenRouter credits or prefer a single API key for all models.",
        "pros": ["Same quality as direct Anthropic", "Single API key for all models", "Actual cost in API response"],
        "cons": ["Slightly higher latency (extra hop)", "Same price as direct"],
    },
    {
        "id": "anthropic/claude-haiku-4.5", "name": "Claude Haiku 4 (OpenRouter)", "provider": "openrouter",
        "price": "$0.80 / $4 per Mtok", "cost_per_run": "~$0.05-0.10",
        "quality": "good", "speed": "fast",
        "description": "Claude Haiku via OpenRouter. Fast and cheap for MBSE model generation.",
        "pros": ["Cheap", "Fast", "Good quality"],
        "cons": ["Shallower reasoning than Sonnet"],
    },
    {
        "id": "google/gemini-2.5-flash", "name": "Gemini 2.5 Flash", "provider": "openrouter",
        "price": "$0.15 / $0.60 per Mtok", "cost_per_run": "~$0.01-0.03",
        "quality": "good", "speed": "very fast",
        "description": "Extremely cheap with surprisingly good structured output. Best option for bulk MBSE model generation runs where cost matters most. May need prompt tuning for best results.",
        "pros": ["20x cheaper than Sonnet", "Very fast", "Good JSON output"],
        "cons": ["Less domain expertise", "May produce generic MBSE model structures"],
    },
    {
        "id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "provider": "openrouter",
        "price": "$1.25 / $10 per Mtok", "cost_per_run": "~$0.10-0.25",
        "quality": "very good", "speed": "medium",
        "description": "Strong reasoning at moderate cost. Good balance between quality and price for MBSE model generation batch processing.",
        "pros": ["Strong reasoning", "Good structured output", "Cheaper than Claude Sonnet"],
        "cons": ["Less tested for this domain", "Slower than Flash"],
    },
    {
        "id": "deepseek/deepseek-chat-v3-0324", "name": "DeepSeek V3", "provider": "openrouter",
        "price": "$0.27 / $1.10 per Mtok", "cost_per_run": "~$0.02-0.05",
        "quality": "good", "speed": "fast",
        "description": "Very cheap with strong reasoning capabilities. Good budget option for MBSE model generation. May occasionally produce less polished output formatting.",
        "pros": ["Very cheap", "Strong reasoning for the price", "Good at following complex instructions"],
        "cons": ["Output formatting can vary", "Less polished MBSE model structures"],
    },
    {
        "id": "deepseek/deepseek-r1", "name": "DeepSeek R1 Reasoner", "provider": "openrouter",
        "price": "$0.55 / $2.19 per Mtok", "cost_per_run": "~$0.05-0.15",
        "quality": "very good", "speed": "slow",
        "description": "Chain-of-thought reasoning model. Excels at complex MBSE model generation logic but slower due to extended thinking. Good for difficult systems engineering problems.",
        "pros": ["Deep reasoning", "Good at complex MBSE modelling", "Cheap for the quality"],
        "cons": ["Slower (thinks before answering)", "May over-think simple model structures"],
    },
    {
        "id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openrouter",
        "price": "$0.15 / $0.60 per Mtok", "cost_per_run": "~$0.01-0.03",
        "quality": "fair", "speed": "very fast",
        "description": "Cheapest option. Fast but may produce shallower MBSE model structures and less precise diagram data. Good for quick tests.",
        "pros": ["Cheapest available", "Very fast"],
        "cons": ["Shallower MBSE model generation", "May miss schema compliance details", "Generic model structures"],
    },
    {
        "id": "openai/gpt-4o", "name": "GPT-4o", "provider": "openrouter",
        "price": "$2.50 / $10 per Mtok", "cost_per_run": "~$0.15-0.35",
        "quality": "very good", "speed": "medium",
        "description": "Strong general-purpose model. Good quality at moderate cost for MBSE model generation. Well-tested for structured output.",
        "pros": ["Strong quality", "Reliable structured output", "Well-documented"],
        "cons": ["Not as strong as Claude for systems engineering domain", "Higher cost than budget options"],
    },
    {
        "id": "meta-llama/llama-4-maverick", "name": "Llama 4 Maverick", "provider": "openrouter",
        "price": "$0.20 / $0.60 per Mtok", "cost_per_run": "~$0.01-0.04",
        "quality": "good", "speed": "fast",
        "description": "Open-source model, very cheap. Good for experimentation and bulk MBSE model generation runs where cost is the priority.",
        "pros": ["Very cheap", "Open source", "Fast"],
        "cons": ["Less tested for this domain", "May need prompt tuning"],
    },
    {
        "id": "qwen/qwen3-235b-a22b", "name": "Qwen 3 235B (MoE)", "provider": "openrouter",
        "price": "$0.20 / $0.60 per Mtok", "cost_per_run": "~$0.01-0.04",
        "quality": "very good", "speed": "medium",
        "description": "Massive 235B mixture-of-experts model at a very low price. Strong reasoning and structured output for MBSE model generation. One of the best quality-per-dollar options available.",
        "pros": ["Excellent quality for the price", "Strong reasoning (235B MoE)", "Good structured output", "Very cheap"],
        "cons": ["Newer model, less battle-tested", "Slightly slower than smaller variants"],
    },
    {
        "id": "qwen/qwen3-32b", "name": "Qwen 3 32B", "provider": "openrouter",
        "price": "$0.10 / $0.30 per Mtok", "cost_per_run": "~$0.01-0.02",
        "quality": "good", "speed": "fast",
        "description": "Dense 32B model. Extremely cheap with solid quality for MBSE model generation. Great for bulk processing where you want a balance of speed, quality, and cost.",
        "pros": ["Extremely cheap", "Fast", "Good quality for size", "Reliable structured output"],
        "cons": ["Smaller model, less nuanced reasoning", "May produce simpler MBSE model structures"],
    },
    {
        "id": "qwen/qwen3-30b-a3b", "name": "Qwen 3 30B (MoE, 3B active)", "provider": "openrouter",
        "price": "$0.05 / $0.15 per Mtok", "cost_per_run": "~$0.005-0.01",
        "quality": "fair", "speed": "very fast",
        "description": "Ultra-cheap MoE model with only 3B active parameters. The cheapest option in the catalogue. Good for rapid prototyping and testing MBSE model generation prompt changes.",
        "pros": ["Cheapest model available", "Extremely fast", "Good for testing"],
        "cons": ["Smallest active parameters", "May struggle with complex MBSE model generation", "Simpler model output"],
    },
]

# Capella architecture layers
CAPELLA_LAYERS = {
    "operational_analysis": "Operational Analysis (OA)",
    "system_needs_analysis": "System Needs Analysis (SA)",
    "logical_architecture": "Logical Architecture (LA)",
    "physical_architecture": "Physical Architecture (PA)",
    "epbs": "End-Product Breakdown Structure (EPBS)",
}

# Rhapsody diagram types
RHAPSODY_DIAGRAMS = {
    "requirements_diagram": "Requirements Diagram",
    "block_definition": "Block Definition Diagram (BDD)",
    "internal_block": "Internal Block Diagram (IBD)",
    "activity_diagram": "Activity Diagram",
    "sequence_diagram": "Sequence Diagram",
    "state_machine": "State Machine Diagram",
}
