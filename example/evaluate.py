import torch
import torchvision
import transformers
from transformers.modeling_outputs import CausalLMOutputWithPast
import torchKQI
import pandas as pd
import traceback
import argparse
import os
from tqdm import tqdm
import numpy as np


Llama_2_7b_hf = {
    "_name_or_path": "meta-llama/Llama-2-7b-hf",
    "architectures": [
        "LlamaForCausalLM"
    ],
    "bos_token_id": 1,
    "eos_token_id": 2,
    "hidden_act": "silu",
    "hidden_size": 4096,
    "initializer_range": 0.02,
    "intermediate_size": 11008,
    "max_position_embeddings": 4096,
    "model_type": "llama",
    "num_attention_heads": 32,
    "num_hidden_layers": 32,
    "num_key_value_heads": 32,
    "pretraining_tp": 1,
    "rms_norm_eps": 1e-05,
    "rope_scaling": None,
    "tie_word_embeddings": False,
    "torch_dtype": "float16",
    "transformers_version": "4.31.0.dev0",
    "use_cache": True,
    "vocab_size": 32000
}

Llama_2_13b_hf = {
    "_name_or_path": "meta-llama/Llama-2-13b-hf",
    "architectures": [
        "LlamaForCausalLM"
    ],
    "bos_token_id": 1,
    "eos_token_id": 2,
    "hidden_act": "silu",
    "hidden_size": 5120,
    "initializer_range": 0.02,
    "intermediate_size": 13824,
    "max_position_embeddings": 4096,
    "model_type": "llama",
    "num_attention_heads": 40,
    "num_hidden_layers": 40,
    "num_key_value_heads": 40,
    "pretraining_tp": 1,
    "rms_norm_eps": 1e-05,
    "rope_scaling": None,
    "tie_word_embeddings": False,
    "torch_dtype": "float16",
    "transformers_version": "4.32.0.dev0",
    "use_cache": True,
    "vocab_size": 32000
}

Llama_2_70b_hf = {
    "_name_or_path": "meta-llama/Llama-2-70b-hf",
    "architectures": [
        "LlamaForCausalLM"
    ],
    "bos_token_id": 1,
    "eos_token_id": 2,
    "hidden_act": "silu",
    "hidden_size": 8192,
    "initializer_range": 0.02,
    "intermediate_size": 28672,
    "max_position_embeddings": 4096,
    "model_type": "llama",
    "num_attention_heads": 64,
    "num_hidden_layers": 80,
    "num_key_value_heads": 8,
    "pretraining_tp": 1,
    "rms_norm_eps": 1e-05,
    "rope_scaling": None,
    "tie_word_embeddings": False,
    "torch_dtype": "float16",
    "transformers_version": "4.32.0.dev0",
    "use_cache": True,
    "vocab_size": 32000
}

Meta_Llama_3_8B = {
    "architectures": [
        "LlamaForCausalLM"
    ],
    "attention_bias": False,
    "attention_dropout": 0.0,
    "bos_token_id": 128000,
    "eos_token_id": 128001,
    "hidden_act": "silu",
    "hidden_size": 4096,
    "initializer_range": 0.02,
    "intermediate_size": 14336,
    "max_position_embeddings": 8192,
    "model_type": "llama",
    "num_attention_heads": 32,
    "num_hidden_layers": 32,
    "num_key_value_heads": 8,
    "pretraining_tp": 1,
    "rms_norm_eps": 1e-05,
    "rope_scaling": None,
    "rope_theta": 500000.0,
    "tie_word_embeddings": False,
    "torch_dtype": "bfloat16",
    "transformers_version": "4.40.0.dev0",
    "use_cache": True,
    "vocab_size": 128256
}

Llama_3_2_1B_Instruct = {
    "architectures": [
        "LlamaForCausalLM"
    ],
    "attention_bias": False,
    "attention_dropout": 0.0,
    "bos_token_id": 128000,
    "eos_token_id": [
        128001,
        128008,
        128009
    ],
    "head_dim": 64,
    "hidden_act": "silu",
    "hidden_size": 2048,
    "initializer_range": 0.02,
    "intermediate_size": 8192,
    "max_position_embeddings": 131072,
    "mlp_bias": False,
    "model_type": "llama",
    "num_attention_heads": 32,
    "num_hidden_layers": 16,
    "num_key_value_heads": 8,
    "pretraining_tp": 1,
    "rms_norm_eps": 1e-05,
    "rope_scaling": {
        "factor": 32.0,
        "high_freq_factor": 4.0,
        "low_freq_factor": 1.0,
        "original_max_position_embeddings": 8192,
        "rope_type": "llama3"
    },
    "rope_theta": 500000.0,
    "tie_word_embeddings": True,
    "torch_dtype": "bfloat16",
    "transformers_version": "4.45.0.dev0",
    "use_cache": True,
    "vocab_size": 128256
}

bert_base_uncased = {
    "architectures": [
        "BertForMaskedLM"
    ],
    "attention_probs_dropout_prob": 0.1,
    "gradient_checkpointing": False,
    "hidden_act": "gelu",
    "hidden_dropout_prob": 0.1,
    "hidden_size": 768,
    "initializer_range": 0.02,
    "intermediate_size": 3072,
    "layer_norm_eps": 1e-12,
    "max_position_embeddings": 512,
    "model_type": "bert",
    "num_attention_heads": 12,
    "num_hidden_layers": 12,
    "pad_token_id": 0,
    "position_embedding_type": "absolute",
    "transformers_version": "4.6.0.dev0",
    "type_vocab_size": 2,
    "use_cache": True,
    "vocab_size": 30522
}

bert_large_uncased = {
    "architectures": [
        "BertForMaskedLM"
    ],
    "attention_probs_dropout_prob": 0.1,
    "gradient_checkpointing": False,
    "hidden_act": "gelu",
    "hidden_dropout_prob": 0.1,
    "hidden_size": 1024,
    "initializer_range": 0.02,
    "intermediate_size": 4096,
    "layer_norm_eps": 1e-12,
    "max_position_embeddings": 512,
    "model_type": "bert",
    "num_attention_heads": 16,
    "num_hidden_layers": 24,
    "pad_token_id": 0,
    "position_embedding_type": "absolute",
    "transformers_version": "4.6.0.dev0",
    "type_vocab_size": 2,
    "use_cache": True,
    "vocab_size": 30522
}

t5_small = {
    "architectures": [
        "T5ForConditionalGeneration"
    ],
    "d_ff": 2048,
    "d_kv": 64,
    "d_model": 512,
    "decoder_start_token_id": 0,
    "dropout_rate": 0.1,
    "eos_token_id": 1,
    "initializer_factor": 1.0,
    "is_encoder_decoder": True,
    "layer_norm_epsilon": 1e-06,
    "model_type": "t5",
    "n_positions": 512,
    "num_heads": 8,
    "num_layers": 6,
    "output_past": True,
    "pad_token_id": 0,
    "relative_attention_num_buckets": 32,
    "task_specific_params": {
        "summarization": {
            "early_stopping": True,
            "length_penalty": 2.0,
            "max_length": 200,
            "min_length": 30,
            "no_repeat_ngram_size": 3,
            "num_beams": 4,
            "prefix": "summarize: "
        },
        "translation_en_to_de": {
            "early_stopping": True,
            "max_length": 300,
            "num_beams": 4,
            "prefix": "translate English to German: "
        },
        "translation_en_to_fr": {
            "early_stopping": True,
            "max_length": 300,
            "num_beams": 4,
            "prefix": "translate English to French: "
        },
        "translation_en_to_ro": {
            "early_stopping": True,
            "max_length": 300,
            "num_beams": 4,
            "prefix": "translate English to Romanian: "
        }
    },
    "vocab_size": 32128
}

t5_base = {
    "architectures": [
        "T5ForConditionalGeneration"
    ],
    "d_ff": 3072,
    "d_kv": 64,
    "d_model": 768,
    "decoder_start_token_id": 0,
    "dropout_rate": 0.1,
    "eos_token_id": 1,
    "initializer_factor": 1.0,
    "is_encoder_decoder": True,
    "layer_norm_epsilon": 1e-06,
    "model_type": "t5",
    "n_positions": 512,
    "num_heads": 12,
    "num_layers": 12,
    "output_past": True,
    "pad_token_id": 0,
    "relative_attention_num_buckets": 32,
    "task_specific_params": {
        "summarization": {
            "early_stopping": True,
            "length_penalty": 2.0,
            "max_length": 200,
            "min_length": 30,
            "no_repeat_ngram_size": 3,
            "num_beams": 4,
            "prefix": "summarize: "
        },
        "translation_en_to_de": {
            "early_stopping": True,
            "max_length": 300,
            "num_beams": 4,
            "prefix": "translate English to German: "
        },
        "translation_en_to_fr": {
            "early_stopping": True,
            "max_length": 300,
            "num_beams": 4,
            "prefix": "translate English to French: "
        },
        "translation_en_to_ro": {
            "early_stopping": True,
            "max_length": 300,
            "num_beams": 4,
            "prefix": "translate English to Romanian: "
        }
    },
    "vocab_size": 32128
}

t5_large = {
    "architectures": [
        "T5ForConditionalGeneration"
    ],
    "d_ff": 4096,
    "d_kv": 64,
    "d_model": 1024,
    "decoder_start_token_id": 0,
    "dropout_rate": 0.1,
    "eos_token_id": 1,
    "initializer_factor": 1.0,
    "is_encoder_decoder": True,
    "layer_norm_epsilon": 1e-06,
    "model_type": "t5",
    "n_positions": 512,
    "num_heads": 16,
    "num_layers": 24,
    "output_past": True,
    "pad_token_id": 0,
    "relative_attention_num_buckets": 32,
    "task_specific_params": {
        "summarization": {
            "early_stopping": True,
            "length_penalty": 2.0,
            "max_length": 200,
            "min_length": 30,
            "no_repeat_ngram_size": 3,
            "num_beams": 4,
            "prefix": "summarize: "
        },
        "translation_en_to_de": {
            "early_stopping": True,
            "max_length": 300,
            "num_beams": 4,
            "prefix": "translate English to German: "
        },
        "translation_en_to_fr": {
            "early_stopping": True,
            "max_length": 300,
            "num_beams": 4,
            "prefix": "translate English to French: "
        },
        "translation_en_to_ro": {
            "early_stopping": True,
            "max_length": 300,
            "num_beams": 4,
            "prefix": "translate English to Romanian: "
        }
    },
    "vocab_size": 32128
}

gemma_2_2b = {
    "architectures": [
        "Gemma2ForCausalLM"
    ],
    "attention_bias": False,
    "attention_dropout": 0.0,
    "attn_logit_softcapping": 50.0,
    "bos_token_id": 2,
    "cache_implementation": "hybrid",
    "eos_token_id": 1,
    "final_logit_softcapping": 30.0,
    "head_dim": 256,
    "hidden_act": "gelu_pytorch_tanh",
    "hidden_activation": "gelu_pytorch_tanh",
    "hidden_size": 2304,
    "initializer_range": 0.02,
    "intermediate_size": 9216,
    "max_position_embeddings": 8192,
    "model_type": "gemma2",
    "num_attention_heads": 8,
    "num_hidden_layers": 26,
    "num_key_value_heads": 4,
    "pad_token_id": 0,
    "query_pre_attn_scalar": 256,
    "rms_norm_eps": 1e-06,
    "rope_theta": 10000.0,
    "sliding_window": 4096,
    "torch_dtype": "float32",
    "transformers_version": "4.42.4",
    "use_cache": True,
    "vocab_size": 256000
}

gemma_2_9b = {
    "architectures": [
        "Gemma2ForCausalLM"
    ],
    "attention_bias": False,
    "attention_dropout": 0.0,
    "attn_logit_softcapping": 50.0,
    "bos_token_id": 2,
    "cache_implementation": "hybrid",
    "eos_token_id": 1,
    "final_logit_softcapping": 30.0,
    "head_dim": 256,
    "hidden_act": "gelu_pytorch_tanh",
    "hidden_activation": "gelu_pytorch_tanh",
    "hidden_size": 3584,
    "initializer_range": 0.02,
    "intermediate_size": 14336,
    "max_position_embeddings": 8192,
    "model_type": "gemma2",
    "num_attention_heads": 16,
    "num_hidden_layers": 42,
    "num_key_value_heads": 8,
    "pad_token_id": 0,
    "query_pre_attn_scalar": 256,
    "rms_norm_eps": 1e-06,
    "rope_theta": 10000.0,
    "sliding_window": 4096,
    "sliding_window_size": 4096,
    "torch_dtype": "float32",
    "transformers_version": "4.42.0.dev0",
    "use_cache": True,
    "vocab_size": 256000
}

gpt = {
    "afn": "gelu",
    "architectures": [
        "OpenAIGPTLMHeadModel"
    ],
    "attn_pdrop": 0.1,
    "embd_pdrop": 0.1,
    "initializer_range": 0.02,
    "layer_norm_epsilon": 1e-05,
    "model_type": "openai-gpt",
    "n_ctx": 512,
    "n_embd": 768,
    "n_head": 12,
    "n_layer": 12,
    "n_positions": 512,
    "n_special": 0,
    "predict_special_tokens": True,
    "resid_pdrop": 0.1,
    "summary_activation": None,
    "summary_first_dropout": 0.1,
    "summary_proj_to_labels": True,
    "summary_type": "cls_index",
    "summary_use_proj": True,
    "task_specific_params": {
        "text-generation": {
            "do_sample": True,
            "max_length": 50
        }
    },
    "vocab_size": 40478
}

gpt2 = {
    "activation_function": "gelu_new",
    "architectures": [
        "GPT2LMHeadModel"
    ],
    "attn_pdrop": 0.1,
    "bos_token_id": 50256,
    "embd_pdrop": 0.1,
    "eos_token_id": 50256,
    "initializer_range": 0.02,
    "layer_norm_epsilon": 1e-05,
    "model_type": "gpt2",
    "n_ctx": 1024,
    "n_embd": 768,
    "n_head": 12,
    "n_layer": 12,
    "n_positions": 1024,
    "resid_pdrop": 0.1,
    "summary_activation": None,
    "summary_first_dropout": 0.1,
    "summary_proj_to_labels": True,
    "summary_type": "cls_index",
    "summary_use_proj": True,
    "task_specific_params": {
        "text-generation": {
            "do_sample": True,
            "max_length": 50
        }
    },
    "vocab_size": 50257
}

Qwen2_5_1_5B = {
    "architectures": [
        "Qwen2ForCausalLM"
    ],
    "attention_dropout": 0.0,
    "bos_token_id": 151643,
    "eos_token_id": 151643,
    "hidden_act": "silu",
    "hidden_size": 1536,
    "initializer_range": 0.02,
    "intermediate_size": 8960,
    "max_position_embeddings": 131072,
    "max_window_layers": 28,
    "model_type": "qwen2",
    "num_attention_heads": 12,
    "num_hidden_layers": 28,
    "num_key_value_heads": 2,
    "rms_norm_eps": 1e-06,
    "rope_theta": 1000000.0,
    "sliding_window": 131072,
    "tie_word_embeddings": True,
    "torch_dtype": "bfloat16",
    "transformers_version": "4.40.1",
    "use_cache": True,
    "use_mrope": False,
    "use_sliding_window": False,
    "vocab_size": 151936
}

Qwen2_5_7B = {
    "architectures": [
        "Qwen2ForCausalLM"
    ],
    "attention_dropout": 0.0,
    "bos_token_id": 151643,
    "eos_token_id": 151643,
    "hidden_act": "silu",
    "hidden_size": 3584,
    "initializer_range": 0.02,
    "intermediate_size": 18944,
    "max_position_embeddings": 131072,
    "max_window_layers": 28,
    "model_type": "qwen2",
    "num_attention_heads": 28,
    "num_hidden_layers": 28,
    "num_key_value_heads": 4,
    "rms_norm_eps": 1e-06,
    "rope_theta": 1000000.0,
    "sliding_window": 131072,
    "tie_word_embeddings": False,
    "torch_dtype": "bfloat16",
    "transformers_version": "4.40.1",
    "use_cache": True,
    "use_mrope": False,
    "use_sliding_window": False,
    "vocab_size": 152064
}

Qwen2_5_14B = {
    "architectures": [
        "Qwen2ForCausalLM"
    ],
    "attention_dropout": 0.0,
    "bos_token_id": 151643,
    "eos_token_id": 151643,
    "hidden_act": "silu",
    "hidden_size": 5120,
    "initializer_range": 0.02,
    "intermediate_size": 13824,
    "max_position_embeddings": 131072,
    "max_window_layers": 48,
    "model_type": "qwen2",
    "num_attention_heads": 40,
    "num_hidden_layers": 48,
    "num_key_value_heads": 8,
    "rms_norm_eps": 1e-05,
    "rope_theta": 1000000.0,
    "sliding_window": 131072,
    "tie_word_embeddings": False,
    "torch_dtype": "bfloat16",
    "transformers_version": "4.43.1",
    "use_cache": True,
    "use_sliding_window": False,
    "vocab_size": 152064
}

Qwen2_5_32B = {
    "architectures": [
        "Qwen2ForCausalLM"
    ],
    "attention_dropout": 0.0,
    "bos_token_id": 151643,
    "eos_token_id": 151643,
    "hidden_act": "silu",
    "hidden_size": 5120,
    "initializer_range": 0.02,
    "intermediate_size": 27648,
    "max_position_embeddings": 131072,
    "max_window_layers": 64,
    "model_type": "qwen2",
    "num_attention_heads": 40,
    "num_hidden_layers": 64,
    "num_key_value_heads": 8,
    "rms_norm_eps": 1e-05,
    "rope_theta": 1000000.0,
    "sliding_window": 131072,
    "tie_word_embeddings": False,
    "torch_dtype": "bfloat16",
    "transformers_version": "4.43.1",
    "use_cache": True,
    "use_sliding_window": False,
    "vocab_size": 152064
}

Yi_1_5_6B = {
    "architectures": [
        "LlamaForCausalLM"
    ],
    "attention_bias": False,
    "attention_dropout": 0.0,
    "bos_token_id": 1,
    "eos_token_id": 2,
    "hidden_act": "silu",
    "hidden_size": 4096,
    "initializer_range": 0.02,
    "intermediate_size": 11008,
    "max_position_embeddings": 4096,
    "model_type": "llama",
    "num_attention_heads": 32,
    "num_hidden_layers": 32,
    "num_key_value_heads": 4,
    "pad_token_id": 0,
    "pretraining_tp": 1,
    "rms_norm_eps": 1e-06,
    "rope_scaling": None,
    "rope_theta": 5000000.0,
    "tie_word_embeddings": False,
    "torch_dtype": "bfloat16",
    "transformers_version": "4.37.2",
    "use_cache": True,
    "vocab_size": 64000
}

Yi_1_5_34B = {
    "architectures": [
        "LlamaForCausalLM"
    ],
    "attention_bias": False,
    "attention_dropout": 0.0,
    "bos_token_id": 1,
    "eos_token_id": 2,
    "hidden_act": "silu",
    "hidden_size": 7168,
    "initializer_range": 0.02,
    "intermediate_size": 20480,
    "max_position_embeddings": 4096,
    "model_type": "llama",
    "num_attention_heads": 56,
    "num_hidden_layers": 60,
    "num_key_value_heads": 8,
    "pad_token_id": 0,
    "pretraining_tp": 1,
    "rms_norm_eps": 1e-06,
    "rope_scaling": None,
    "rope_theta": 5000000.0,
    "tie_word_embeddings": False,
    "torch_dtype": "bfloat16",
    "transformers_version": "4.37.2",
    "use_cache": True,
    "vocab_size": 64000
}

deepseek_llm_7b_base = {
    "architectures": [
        "LlamaForCausalLM"
    ],
    "bos_token_id": 1,
    "eos_token_id": 2,
    "hidden_act": "silu",
    "hidden_size": 4096,
    "initializer_range": 0.02,
    "intermediate_size": 11008,
    "max_position_embeddings": 4096,
    "model_type": "llama",
    "num_attention_heads": 32,
    "num_hidden_layers": 30,
    "num_key_value_heads": 32,
    "pretraining_tp": 1,
    "rms_norm_eps": 1e-06,
    "rope_scaling": None,
    "rope_theta": 10000.0,
    "tie_word_embeddings": False,
    "torch_dtype": "bfloat16",
    "transformers_version": "4.33.1",
    "use_cache": True,
    "vocab_size": 102400
}

scibert_scivocab_cased = {
    "attention_probs_dropout_prob": 0.1,
    "hidden_act": "gelu",
    "hidden_dropout_prob": 0.1,
    "hidden_size": 768,
    "initializer_range": 0.02,
    "intermediate_size": 3072,
    "layer_norm_eps": 1e-12,
    "max_position_embeddings": 512,
    "model_type": "bert",
    "num_attention_heads": 12,
    "num_hidden_layers": 12,
    "pad_token_id": 0,
    "type_vocab_size": 2,
    "vocab_size": 31116
}

scibert_scivocab_uncased = {
    "attention_probs_dropout_prob": 0.1,
    "hidden_act": "gelu",
    "hidden_dropout_prob": 0.1,
    "hidden_size": 768,
    "initializer_range": 0.02,
    "intermediate_size": 3072,
    "layer_norm_eps": 1e-12,
    "max_position_embeddings": 512,
    "model_type": "bert",
    "num_attention_heads": 12,
    "num_hidden_layers": 12,
    "pad_token_id": 0,
    "type_vocab_size": 2,
    "vocab_size": 31090
}

specter = {
    "_name_or_path": "allenai/scibert_scivocab_cased",
    "architectures": [
        "BertModel"
    ],
    "attention_probs_dropout_prob": 0.1,
    "gradient_checkpointing": False,
    "hidden_act": "gelu",
    "hidden_dropout_prob": 0.1,
    "hidden_size": 768,
    "initializer_range": 0.02,
    "intermediate_size": 3072,
    "layer_norm_eps": 1e-12,
    "max_position_embeddings": 512,
    "model_type": "bert",
    "num_attention_heads": 12,
    "num_hidden_layers": 12,
    "pad_token_id": 0,
    "position_embedding_type": "absolute",
    "transformers_version": "4.2.2",
    "type_vocab_size": 2,
    "use_cache": True,
    "vocab_size": 31116
}

specter2_base = {
    "_name_or_path": "scirepeval/specterv4/checkpoints/model",
    "adapters": {
        "adapters": {},
        "config_map": {},
        "fusion_config_map": {},
        "fusions": {}
    },
    "architectures": [
        "BertModel"
    ],
    "attention_probs_dropout_prob": 0.1,
    "classifier_dropout": None,
    "hidden_act": "gelu",
    "hidden_dropout_prob": 0.1,
    "hidden_size": 768,
    "initializer_range": 0.02,
    "intermediate_size": 3072,
    "layer_norm_eps": 1e-12,
    "max_position_embeddings": 512,
    "model_type": "bert",
    "num_attention_heads": 12,
    "num_hidden_layers": 12,
    "pad_token_id": 0,
    "position_embedding_type": "absolute",
    "torch_dtype": "float32",
    "transformers_version": "4.26.1",
    "type_vocab_size": 2,
    "use_cache": True,
    "vocab_size": 31090
}

scincl = {
    "_name_or_path": "malteos/scincl",
    "architectures": [
        "BertModel"
    ],
    "attention_probs_dropout_prob": 0.1,
    "gradient_checkpointing": False,
    "hidden_act": "gelu",
    "hidden_dropout_prob": 0.1,
    "hidden_size": 768,
    "initializer_range": 0.02,
    "intermediate_size": 3072,
    "layer_norm_eps": 1e-12,
    "max_position_embeddings": 512,
    "model_type": "bert",
    "num_attention_heads": 12,
    "num_hidden_layers": 12,
    "pad_token_id": 0,
    "position_embedding_type": "absolute",
    "transformers_version": "4.5.1",
    "type_vocab_size": 2,
    "use_cache": True,
    "vocab_size": 31090
}

phi_1 = {
    "_name_or_path": "microsoft/phi-1",
    "architectures": [
        "PhiForCausalLM"
    ],
    "attention_dropout": 0.0,
    "bos_token_id": None,
    "embd_pdrop": 0.0,
    "eos_token_id": None,
    "hidden_act": "gelu_new",
    "hidden_size": 2048,
    "initializer_range": 0.02,
    "intermediate_size": 8192,
    "layer_norm_eps": 1e-05,
    "max_position_embeddings": 2048,
    "model_type": "phi",
    "num_attention_heads": 32,
    "num_hidden_layers": 24,
    "num_key_value_heads": None,
    "partial_rotary_factor": 0.5,
    "qk_layernorm": False,
    "resid_pdrop": 0.0,
    "rope_scaling": None,
    "rope_theta": 10000.0,
    "tie_word_embeddings": False,
    "torch_dtype": "float32",
    "transformers_version": "4.37.0",
    "use_cache": True,
    "vocab_size": 51200
}

phi_1_5 = {
    "_name_or_path": "microsoft/phi-1_5",
    "architectures": [
        "PhiForCausalLM"
    ],
    "attention_dropout": 0.0,
    "bos_token_id": None,
    "embd_pdrop": 0.0,
    "eos_token_id": None,
    "hidden_act": "gelu_new",
    "hidden_size": 2048,
    "initializer_range": 0.02,
    "intermediate_size": 8192,
    "layer_norm_eps": 1e-05,
    "max_position_embeddings": 2048,
    "model_type": "phi",
    "num_attention_heads": 32,
    "num_hidden_layers": 24,
    "num_key_value_heads": None,
    "partial_rotary_factor": 0.5,
    "qk_layernorm": False,
    "resid_pdrop": 0.0,
    "rope_scaling": None,
    "rope_theta": 10000.0,
    "tie_word_embeddings": False,
    "torch_dtype": "float16",
    "transformers_version": "4.37.0",
    "use_cache": True,
    "vocab_size": 51200
}

Phi_3_mini_4k_instruct = {
    "_name_or_path": "Phi-3-mini-4k-instruct",
    "architectures": [
        "Phi3ForCausalLM"
    ],
    "attention_dropout": 0.0,
    "auto_map": {
        "AutoConfig": "configuration_phi3.Phi3Config",
        "AutoModelForCausalLM": "modeling_phi3.Phi3ForCausalLM"
    },
    "bos_token_id": 1,
    "embd_pdrop": 0.0,
    "eos_token_id": 32000,
    "hidden_act": "silu",
    "hidden_size": 3072,
    "initializer_range": 0.02,
    "intermediate_size": 8192,
    "max_position_embeddings": 4096,
    "model_type": "phi3",
    "num_attention_heads": 32,
    "num_hidden_layers": 32,
    "num_key_value_heads": 32,
    "original_max_position_embeddings": 4096,
    "pad_token_id": 32000,
    "resid_pdrop": 0.0,
    "rms_norm_eps": 1e-05,
    "rope_scaling": None,
    "rope_theta": 10000.0,
    "sliding_window": 2047,
    "tie_word_embeddings": False,
    "torch_dtype": "bfloat16",
    "transformers_version": "4.40.2",
    "use_cache": True,
    "attention_bias": False,
    "vocab_size": 32064
}


def calculate_kqi_components(kqi, model, x, callback_func = lambda model, x: model(x), device=None, disk_cache_dir=None, model_name=None):
    kqi_list = {}

    for grad_fn, kqis in tqdm(torchKQI.KQI_generator(model, x, callback_func, device=device, disk_cache_dir=disk_cache_dir), desc=f"Processing {model_name}"):
        grad_name = str(grad_fn.name())
        kqi_percentage = sum(map(lambda k: k.sum(), kqis)) / kqi * 100
        num = sum(np.prod(k.size()) for k in kqis)

        target_key = 'parameters' if 'AccumulateGrad' in grad_name else grad_name
        
        if target_key not in kqi_list:
            kqi_list[target_key] = [0.0, 0, 0]

        kqi_list[target_key][0] += kqi_percentage
        kqi_list[target_key][1] += num
        kqi_list[target_key][2] += 1

    result_rows = []
    for key, val in kqi_list.items():
        result_rows.append({
            'Model Name': model_name,
            'grad_fn': key,
            'percentage': float(val[0]),
            'total_num': int(val[1]),
            'times': int(val[2])
        })
    
    return result_rows


def task_ImageClassification(args):
    x = torch.randn(1, 3, 224, 224)

    model_fns = [
        torchvision.models.alexnet,
        torchvision.models.convnext_tiny, torchvision.models.convnext_small, torchvision.models.convnext_base, torchvision.models.convnext_large,
        torchvision.models.densenet121, torchvision.models.densenet161, torchvision.models.densenet169, torchvision.models.densenet201,
        torchvision.models.efficientnet_b0, torchvision.models.efficientnet_b1, torchvision.models.efficientnet_b2, torchvision.models.efficientnet_b3, torchvision.models.efficientnet_b4, torchvision.models.efficientnet_b5, torchvision.models.efficientnet_b6, torchvision.models.efficientnet_b7, torchvision.models.efficientnet_v2_s, torchvision.models.efficientnet_v2_m, torchvision.models.efficientnet_v2_l,
        torchvision.models.googlenet,
        torchvision.models.inception_v3,
        torchvision.models.maxvit_t,
        torchvision.models.mnasnet0_5, torchvision.models.mnasnet0_75, torchvision.models.mnasnet1_0, torchvision.models.mnasnet1_3,
        torchvision.models.mobilenet_v2,
        torchvision.models.mobilenet_v3_large, torchvision.models.mobilenet_v3_small,
        torchvision.models.regnet_y_400mf, torchvision.models.regnet_y_800mf, torchvision.models.regnet_y_1_6gf, torchvision.models.regnet_y_3_2gf, torchvision.models.regnet_y_8gf, torchvision.models.regnet_y_16gf, torchvision.models.regnet_y_32gf, torchvision.models.regnet_y_128gf, torchvision.models.regnet_x_400mf, torchvision.models.regnet_x_800mf, torchvision.models.regnet_x_1_6gf, torchvision.models.regnet_x_3_2gf, torchvision.models.regnet_x_8gf, torchvision.models.regnet_x_16gf, torchvision.models.regnet_x_32gf,
        torchvision.models.resnet18, torchvision.models.resnet34, torchvision.models.resnet50, torchvision.models.resnet101, torchvision.models.resnet152,
        torchvision.models.resnext50_32x4d, torchvision.models.resnext101_32x8d, torchvision.models.resnext101_64x4d,
        torchvision.models.wide_resnet50_2, torchvision.models.wide_resnet101_2,
        torchvision.models.shufflenet_v2_x0_5, torchvision.models.shufflenet_v2_x1_0, torchvision.models.shufflenet_v2_x1_5, torchvision.models.shufflenet_v2_x2_0,
        torchvision.models.squeezenet1_0, torchvision.models.squeezenet1_1,
        torchvision.models.swin_t, torchvision.models.swin_s, torchvision.models.swin_b, torchvision.models.swin_v2_t, torchvision.models.swin_v2_s, torchvision.models.swin_v2_b,
        torchvision.models.vgg11, torchvision.models.vgg11_bn, torchvision.models.vgg13, torchvision.models.vgg13_bn, torchvision.models.vgg16, torchvision.models.vgg16_bn, torchvision.models.vgg19, torchvision.models.vgg19_bn,
        torchvision.models.vit_b_16, torchvision.models.vit_b_32, torchvision.models.vit_l_16, torchvision.models.vit_l_32, torchvision.models.vit_h_14
    ]

    results_file_kqi = f'{args.output_path}/ImageClassification_results_kqi.csv'
    results_file_component = f'{args.output_path}/ImageClassification_results_component.csv'
    errors_file = f'{args.output_path}/ImageClassification_errors.csv'

    if not os.path.exists(results_file_kqi):
        pd.DataFrame(columns=['Model Name', 'KQI']).to_csv(results_file_kqi, index=False)
    if not os.path.exists(results_file_component):
        pd.DataFrame(columns=['Model Name', 'grad_fn', 'percentage', 'total_num', 'times']).to_csv(results_file_component, index=False)
    if not os.path.exists(errors_file):
        pd.DataFrame(columns=['Model Name', 'Error']).to_csv(errors_file, index=False)

    for model_fn in model_fns:
        if model_fn.__name__ in pd.read_csv(results_file_kqi)['Model Name'].values:
            continue
        try:
            model = model_fn().eval()
            kqi = torchKQI.KQI(model, x, device=args.gpu).item()
            result = pd.DataFrame([[model_fn.__name__, kqi]], columns=['Model Name', 'KQI'])
            result.to_csv(results_file_kqi, mode='a', header=False, index=False)

            result_rows = calculate_kqi_components(kqi, model, x, device=args.gpu, disk_cache_dir=args.disk_cache_dir, model_name=model_fn.__name__)
            result = pd.DataFrame(result_rows)
            result.to_csv(results_file_component, mode='a', index=False, header=False)

        except Exception:
            error = pd.DataFrame([[model_fn.__name__, traceback.format_exc()]], columns=['Model Name', 'Error'])
            error.to_csv(errors_file, mode='a', header=False, index=False)


def task_SemanticSegmentation(args):
    x = torch.randn(1, 3, 224, 224)

    model_fns = [
        torchvision.models.segmentation.deeplabv3_mobilenet_v3_large, torchvision.models.segmentation.deeplabv3_resnet50, torchvision.models.segmentation.deeplabv3_resnet101,
        torchvision.models.segmentation.fcn_resnet50, torchvision.models.segmentation.fcn_resnet101,
        torchvision.models.segmentation.lraspp_mobilenet_v3_large,
    ]

    results_file_kqi = f'{args.output_path}/SemanticSegmentation_results_kqi.csv'
    results_file_component = f'{args.output_path}/SemanticSegmentation_results_component.csv'
    errors_file = f'{args.output_path}/SemanticSegmentation_errors.csv'

    if not os.path.exists(results_file_kqi):
        pd.DataFrame(columns=['Model Name', 'KQI']).to_csv(results_file_kqi, index=False)
    if not os.path.exists(results_file_component):
        pd.DataFrame(columns=['Model Name', 'grad_fn', 'percentage', 'total_num', 'times']).to_csv(results_file_component, index=False)
    if not os.path.exists(errors_file):
        pd.DataFrame(columns=['Model Name', 'Error']).to_csv(errors_file, index=False)

    for model_fn in model_fns:
        if model_fn.__name__ in pd.read_csv(results_file_kqi)['Model Name'].values:
            continue
        try:
            model = model_fn().eval()
            kqi = torchKQI.KQI(model, x, lambda model, x: model(x)['out'], device=args.gpu).item()
            result = pd.DataFrame([[model_fn.__name__, kqi]], columns=['Model Name', 'KQI'])
            result.to_csv(results_file_kqi, mode='a', header=False, index=False)

            result_rows = calculate_kqi_components(kqi, model, x, lambda model, x: model(x)['out'], device=args.gpu, disk_cache_dir=args.disk_cache_dir, model_name=model_fn.__name__)
            result = pd.DataFrame(result_rows)
            result.to_csv(results_file_component, mode='a', index=False, header=False)

        except Exception:
            error = pd.DataFrame([[model_fn.__name__, traceback.format_exc()]], columns=['Model Name', 'Error'])
            error.to_csv(errors_file, mode='a', header=False, index=False)


def task_ObjectDetection(args):
    x = torch.randn(1, 3, 300, 300)

    model_fns = [
        torchvision.models.detection.fasterrcnn_resnet50_fpn, torchvision.models.detection.fasterrcnn_mobilenet_v3_large_fpn, torchvision.models.detection.fasterrcnn_mobilenet_v3_large_320_fpn, torchvision.models.detection.fasterrcnn_resnet50_fpn_v2,
        torchvision.models.detection.fcos_resnet50_fpn,
        torchvision.models.detection.retinanet_resnet50_fpn, torchvision.models.detection.retinanet_resnet50_fpn_v2,
        torchvision.models.detection.ssdlite320_mobilenet_v3_large,
    ]

    results_file_kqi = f'{args.output_path}/ObjectDetection_results_kqi.csv'
    results_file_component = f'{args.output_path}/ObjectDetection_results_component.csv'
    errors_file = f'{args.output_path}/ObjectDetection_errors.csv'

    if not os.path.exists(results_file_kqi):
        pd.DataFrame(columns=['Model Name', 'KQI']).to_csv(results_file_kqi, index=False)
    if not os.path.exists(results_file_component):
        pd.DataFrame(columns=['Model Name', 'grad_fn', 'percentage', 'total_num', 'times']).to_csv(results_file_component, index=False)
    if not os.path.exists(errors_file):
        pd.DataFrame(columns=['Model Name', 'Error']).to_csv(errors_file, index=False)

    for model_fn in model_fns:
        if model_fn.__name__ in pd.read_csv(results_file_kqi)['Model Name'].values:
            continue
        try:
            model = model_fn().eval()
            kqi = torchKQI.KQI(model, x, lambda model, x: model(x)[0]['boxes'], device=args.gpu).item()
            result = pd.DataFrame([[model_fn.__name__, kqi]], columns=['Model Name', 'KQI'])
            result.to_csv(results_file_kqi, mode='a', header=False, index=False)
            
            result_rows = calculate_kqi_components(kqi, model, x, lambda model, x: model(x)[0]['boxes'], device=args.gpu, disk_cache_dir=args.disk_cache_dir, model_name=model_fn.__name__)
            result = pd.DataFrame(result_rows)
            result.to_csv(results_file_component, mode='a', index=False, header=False)
            
        except Exception:
            error = pd.DataFrame([[model_fn.__name__, traceback.format_exc()]], columns=['Model Name', 'Error'])
            error.to_csv(errors_file, mode='a', header=False, index=False)


def task_VideoClassification(args):
    x = torch.randn(1, 3, 16, 224, 224)

    model_fns = [
        torchvision.models.video.mvit_v1_b, torchvision.models.video.mvit_v2_s,
        torchvision.models.video.r3d_18, torchvision.models.video.mc3_18, torchvision.models.video.r2plus1d_18,
        torchvision.models.video.s3d,
        torchvision.models.video.swin3d_t, torchvision.models.video.swin3d_s, torchvision.models.video.swin3d_b
    ]

    results_file_kqi = f'{args.output_path}/VideoClassification_results_kqi.csv'
    results_file_component = f'{args.output_path}/VideoClassification_results_component.csv'
    errors_file = f'{args.output_path}/VideoClassification_errors.csv'

    if not os.path.exists(results_file_kqi):
        pd.DataFrame(columns=['Model Name', 'KQI']).to_csv(results_file_kqi, index=False)
    if not os.path.exists(results_file_component):
        pd.DataFrame(columns=['Model Name', 'grad_fn', 'percentage', 'total_num', 'times']).to_csv(results_file_component, index=False)
    if not os.path.exists(errors_file):
        pd.DataFrame(columns=['Model Name', 'Error']).to_csv(errors_file, index=False)

    for model_fn in model_fns:
        if model_fn.__name__ in pd.read_csv(results_file_kqi)['Model Name'].values:
            continue
        try:
            model = model_fn().eval()
            kqi = torchKQI.KQI(model, x, device=args.gpu).item()
            result = pd.DataFrame([[model_fn.__name__, kqi]], columns=['Model Name', 'KQI'])
            result.to_csv(results_file_kqi, mode='a', header=False, index=False)
            
            result_rows = calculate_kqi_components(kqi, model, x, device=args.gpu, disk_cache_dir=args.disk_cache_dir, model_name=model_fn.__name__)
            result = pd.DataFrame(result_rows)
            result.to_csv(results_file_component, mode='a', index=False, header=False)

        except Exception:
            error = pd.DataFrame([[model_fn.__name__, traceback.format_exc()]], columns=['Model Name', 'Error'])
            error.to_csv(errors_file, mode='a', header=False, index=False)


def task_LLM(args):
    llm_configs = {
        "bert_base_uncased": (bert_base_uncased, transformers.BertConfig),
        "bert_large_uncased": (bert_large_uncased, transformers.BertConfig),
        "scibert_scivocab_cased": (scibert_scivocab_cased, transformers.BertConfig),
        "scibert_scivocab_uncased": (scibert_scivocab_uncased, transformers.BertConfig),
        "specter": (specter, transformers.BertConfig),
        "specter2_base": (specter2_base, transformers.BertConfig),
        "scincl": (scincl, transformers.BertConfig),
        "t5_small": (t5_small, transformers.T5Config),
        "t5_base": (t5_base, transformers.T5Config),
        "t5_large": (t5_large, transformers.T5Config),
        "gpt": (gpt, transformers.OpenAIGPTConfig),
        "gpt2": (gpt2, transformers.GPT2Config),
        "Llama_2_7b_hf": (Llama_2_7b_hf, transformers.LlamaConfig),
        "Llama_2_13b_hf": (Llama_2_13b_hf, transformers.LlamaConfig),
        "Llama_2_70b_hf": (Llama_2_70b_hf, transformers.LlamaConfig),
        "Meta_Llama_3_8B": (Meta_Llama_3_8B, transformers.LlamaConfig),
        "Llama_3_2_1B_Instruct": (Llama_3_2_1B_Instruct, transformers.LlamaConfig),
        "deepseek_llm_7b_base": (deepseek_llm_7b_base, transformers.LlamaConfig),
        "gemma_2_2b": (gemma_2_2b, transformers.Gemma2Config),
        "gemma_2_9b": (gemma_2_9b, transformers.Gemma2Config),
        "Qwen2_5_1_5B": (Qwen2_5_1_5B, transformers.Qwen2Config),
        "Qwen2_5_7B": (Qwen2_5_7B, transformers.Qwen2Config),
        "Qwen2_5_14B": (Qwen2_5_14B, transformers.Qwen2Config),
        "Qwen2_5_32B": (Qwen2_5_32B, transformers.Qwen2Config),
        "Yi_1_5_6B": (Yi_1_5_6B, transformers.LlamaConfig),
        "Yi_1_5_34B": (Yi_1_5_34B, transformers.LlamaConfig),
        "phi_1": (phi_1, transformers.PhiConfig),
        "phi_1_5": (phi_1_5, transformers.PhiConfig),
        "Phi_3_mini_4k_instruct": (Phi_3_mini_4k_instruct, transformers.Phi3Config),
    }

    results_file_kqi = f'{args.output_path}/LLM_results_kqi.csv'
    results_file_component = f'{args.output_path}/LLM_results_component.csv'
    errors_file = f'{args.output_path}/LLM_errors.csv'

    if not os.path.exists(results_file_kqi):
        pd.DataFrame(columns=['Model Name', 'KQI']).to_csv(results_file_kqi, index=False)
    if not os.path.exists(results_file_component):
        pd.DataFrame(columns=['Model Name', 'grad_fn', 'percentage', 'total_num', 'times']).to_csv(results_file_component, index=False)
    if not os.path.exists(errors_file):
        pd.DataFrame(columns=['Model Name', 'Error']).to_csv(errors_file, index=False)

    for llm_name, llm_config in llm_configs.items():
        if llm_name in pd.read_csv(results_file_kqi)['Model Name'].values:
            continue
        try:
            config = llm_config[1].from_dict(llm_config[0])
            model = transformers.AutoModel.from_config(config).eval()

            if 'max_position_embeddings' in config.__dict__:
                sequence_length = config.max_position_embeddings
            else:
                sequence_length = config.n_positions
            sequence_length = min(sequence_length, 4096)

            batch_size = 1
            if isinstance(config, transformers.T5Config):
                x = {
                    'input_ids': torch.randint(0, config.vocab_size, (batch_size, sequence_length)),
                    'decoder_input_ids': torch.randint(0, config.vocab_size, (batch_size, sequence_length))
                }
                callback_func = lambda model, x: model(**x).last_hidden_state
                kqi = torchKQI.KQI(model, x, callback_func, device=args.gpu, disk_cache_dir=args.disk_cache_dir).item()
            else:
                x = torch.randint(0, config.vocab_size, (batch_size, sequence_length))
                callback_func = lambda model, x: model(x).logits if isinstance(model(x), CausalLMOutputWithPast) else model(x).last_hidden_state

                kqi = torchKQI.KQI(model, x, callback_func, device=args.gpu, disk_cache_dir=args.disk_cache_dir).item()
            result = pd.DataFrame([[llm_name, kqi]], columns=['Model Name', 'KQI'])
            result.to_csv(results_file_kqi, mode='a', header=False, index=False)
            
            result_rows = calculate_kqi_components(kqi, model, x, callback_func, device=args.gpu, disk_cache_dir=args.disk_cache_dir, model_name=llm_name)
            result = pd.DataFrame(result_rows)
            result.to_csv(results_file_component, mode='a', index=False, header=False)

        except Exception:
            error = pd.DataFrame([[llm_name, traceback.format_exc()]], columns=['Model Name', 'Error'])
            error.to_csv(errors_file, mode='a', header=False, index=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Setting GPU and output path.")
    parser.add_argument("--output_path", type=str, required=False, default='./result', help="Output file path.")
    parser.add_argument("--gpu", type=str, required=False, default=None, help="GPU ID (for example, 0 or 0,1). Default to CPU.")
    parser.add_argument("--disk_cache_dir", type=str, required=False, default=None, help="Disk cache to intermediate results. Reduce memory usage, but reduce performance.")
    args = parser.parse_args()
    if args.gpu is None:
        args.gpu = torch.device('cpu')
    else:
        args.gpu = [torch.device(f'cuda:{int(k)}') for k in args.gpu.split(',')]
    if not os.path.exists(args.output_path):
        os.mkdir(args.output_path)

    task_ImageClassification(args)
    task_SemanticSegmentation(args)
    task_ObjectDetection(args)
    task_VideoClassification(args)
    task_LLM(args)
