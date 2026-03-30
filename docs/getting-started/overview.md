# tg-ytdlp-bot Overview

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![PyroTGFork](https://img.shields.io/badge/PyroTGFork-Latest-green.svg)](https://github.com/pyrogram/pyrogram)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-Latest-red.svg)](https://github.com/yt-dlp/yt-dlp)
[![gallery-dl](https://img.shields.io/badge/gallery--dl-Latest-orange.svg)](https://github.com/mikf/gallery-dl)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://t.me/tgytdlp)

## Table of Contents
- [What is tg-ytdlp-bot?](#what-is-tg-ytdlp-bot)
- [Features](#features)
- [Quick Start](#quick-start)
  - [Try the Bot](#try-the-bot)
  - [Basic Usage](#basic-usage)

## What is tg-ytdlp-bot?

**tg-ytdlp-bot** is a powerful Telegram bot that downloads videos, audio, and images from YouTube, TikTok, Instagram, and 1500+ other platforms using yt-dlp and gallery-dl. Features advanced format selection, codec support, intelligent subtitle handling, proxy support, and direct stream links.

## ✨ Features

- 🎬 **1500+ Platforms**: YouTube, TikTok, Instagram, Twitter, Facebook, and many more
- 🌍 **Multi-Language Support**: 4 languages - 🇺🇸 English, 🇷🇺 Русский, 🇸🇦 العربية, 🇮🇳 हिन्दी
- 🍪 **Cookie Support**: Download private/age-restricted content with your own cookies
- 🎯 **Smart Format Selection**: Advanced codec support (H.264/AVC, AV1, VP9) with container preferences
- 📱 **Interactive Menus**: Always Ask quality selection with real-time filtering
- 🔗 **Direct Links**: Get direct stream URLs for media players (VLC, MX Player, etc.)
- 🌐 **Proxy Support**: Global proxy control for all downloads
- 💬 **Subtitle Integration**: Intelligent subtitle handling with language detection
- 🏷️ **Tag System**: Organize your downloads with custom tags
- 📊 **Usage Statistics**: Track your download history and usage
- 🔒 **Privacy Focused**: User-specific settings and secure cookie handling
- 🚀 **PO Token Provider**: Bypass YouTube restrictions automatically
- 🖼️ **Image Support**: Download images from various platforms using gallery-dl
- 🔞 **NSFW Content Management**: Advanced NSFW detection and content filtering
- ⏱️ **Flood Wait Protection**: Smart rate limiting and flood wait handling

## 🚀 Quick Start

### Try the Bot

**Live Demo Bots:**
- 🇮🇹 [@tgytdlp_it_bot](https://t.me/tgytdlp_it_bot) - Main IT bot
- 🇦🇪 [@tgytdlp_uae_bot](https://t.me/tgytdlp_uae_bot) - UAE server
- 🇬🇧 [@tgytdlp_uk_bot](https://t.me/tgytdlp_uk_bot) - UK server
- 🇫🇷 [@tgytdlp_fr_bot](https://t.me/tgytdlp_fr_bot) - FR server

**Community Channel:** [@tg_ytdlp](https://t.me/tg_ytdlp)

### Basic Usage

1. **Send a video URL** to the bot
2. **Choose quality** from the interactive menu
3. **Download** your video with custom settings

```
https://youtube.com/watch?v=dQw4w9WgXcQ
```

## 📋 Table of Contents

- [Installation](installation.md#-docker-deployment-recommended-for-most-users) - How to install the bot using Docker or manually
- [Configuration](../configuration/configuration.md#️-configuration) - Detailed configuration settings
- [User Commands](../commands/user-commands.md#-user-commands) - Complete list of user commands
- [Advanced Features](../advanced/advanced-features.md#️-advanced-features) - Advanced functionality and features
- [Admin Commands](../commands/admin-commands.md#️-admin-commands) - Administrative commands and tools
- [System Formulation](../development/01-system-formulation.md#system-formulation) - PDA-aligned system boundary, invariants, policy, and precedence
- [Data Flow Sequence](../development/02-data-flow-sequence.md#data-flow-sequence) - Runtime actor and request flow from Telegram input to Telegram output
- [Task Model](../development/05-task-model.md#task-model) - Task identity, states, authorities, precedence, and terminal outcomes
- [Task-to-Code Map](../development/06-task-to-code-map.md#task-to-code-map) - Transition ownership map from the task model into concrete modules
- [Branch Selection Model](../development/07-branch-selection-model.md#branch-selection-model) - Explicit formulation of the main decision surface for media tasks
- [Terminal Semantics Model](../development/08-terminal-semantics-model.md#terminal-semantics-model) - Explicit outcome meaning for success, partial success, rejection, and failure
- [Branch Selection Result Model](../development/09-branch-selection-result-model.md#branch-selection-result-model) - Explicit output object for the branch-selection decision surface
- [Terminal Outcome Result Model](../development/10-terminal-outcome-result-model.md#terminal-outcome-result-model) - Explicit output object for terminal outcome meaning
- [Task State Machine Sketch](../development/11-task-state-machine-sketch.md#task-state-machine-sketch) - Closed execution skeleton connecting branch selection and terminal outcome
- [Task Object Model](../development/12-task-object-model.md#task-object-model) - Explicit primary runtime object carrying task identity, state, branch, and outcome
- [Transition Contracts](../development/13-transition-contracts.md#transition-contracts) - Explicit read/write/decision boundaries for each task-state-machine transition
- [First Implementation Seam](../development/14-first-implementation-seam.md#first-implementation-seam) - Why `BranchSelectionResult` is the best low-risk first implementation move
- [Branch Selection Result Implementation Sketch](../development/15-branch-selection-result-implementation-sketch.md#branch-selection-result-implementation-sketch) - Smallest viable first patch for making branch selection explicit
- [Video Concat Formulation](../development/16-video-concat-formulation.md#video-concat-formulation) - PDA-aligned branch/task/outcome formulation for future video concat
- [Video Concat Admissibility Contract](../development/17-video-concat-admissibility-contract.md#video-concat-admissibility-contract) - Explicit admissibility boundary for selecting and executing video concat
- [Video Concat First Implementation Seam](../development/18-video-concat-first-implementation-seam.md#video-concat-first-implementation-seam) - Smallest coherent implementation boundary for `video_concat_download`
- [Video Concat Compatibility Model](../development/19-video-concat-compatibility-model.md#video-concat-compatibility-model) - Explicit direct-concat compatibility predicate and rejection boundary for v1 video concat
- [Video Concat Compatibility Result Model](../development/20-video-concat-compatibility-result-model.md#video-concat-compatibility-result-model) - Explicit result object for concat admissibility and determinate rejection
- [Video Concat Transition Contract](../development/21-video-concat-transition-contract.md#video-concat-transition-contract) - Explicit first state/transition contract from concat request through terminalization
- [Video Concat Staging Manifest Model](../development/22-video-concat-staging-manifest-model.md#video-concat-staging-manifest-model) - Explicit staging carrier for selected indices, ordered artifacts, and missing items
- [Video Concat Terminal Rendering Contract](../development/23-video-concat-terminal-rendering-contract.md#video-concat-terminal-rendering-contract) - Explicit user/log rendering rules for concat success, rejection, and failure
- [Video Concat Chapter Policy Model](../development/24-video-concat-chapter-policy-model.md#video-concat-chapter-policy-model) - Explicit policy separation for playlist-item chapter metadata on composite video output
- [Video Concat Object Chain Implementation Sketch](../development/25-video-concat-object-chain-implementation-sketch.md#video-concat-object-chain-implementation-sketch) - First coherent implementation sketch for branch, manifest, compatibility, concat execution, and terminal outcome
- [Video Concat Policy Partition](../development/26-video-concat-policy-partition.md#video-concat-policy-partition) - Explicit separation of concat admissibility, delivery admissibility, and terminal rendering policy
- [Troubleshooting](../advanced/troubleshooting.md#-troubleshooting) - Common issues and solutions
- [Contributing](../development/04-contributing.md#-code-of-conduct) - How to contribute to the project
- [Support](../misc/support.md#support) - Support information and acknowledgments
