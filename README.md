# Chess Game Analysis Tool

## Overview
This project provides tools for analyzing chess games by connecting to the Lichess platform and utilizing a local chess engine. It features two main classes, `Player` and `GameAnalysis`, which allow users to fetch game data from Lichess, analyze it, and display detailed insights about mistakes, game phases, and specific endgame scenarios.

## Features
- Fetch player profiles and game data from Lichess using the `berserk` API client.
- Analyze chess games using a local chess engine to evaluate player mistakes and critical game moments.
- Identify and categorize game phases and specific tactics such as pins, promotions, and checkmates.
- Aggregate and display analysis results, highlighting frequent mistake types and themes.

## Installation

To use this tool, you need Python installed on your machine along with the following packages:

### Libraries
Install the necessary Python libraries using pip:

```bash
pip install -r 'requirements.txt'
```

## Usage
### Setting Up the Player
To analyze games from Lichess, you must create a Player object with your API token and username:

```bash
from main.py import Player

api_token = 'your_lichess_api_token_here'
username = 'your_lichess_username_here'
engine_path = '/path/to/your/chess/engine'  # Optional, not needed for now, default=None

player = Player(api_token, username, engine_path)
player.analyze_games()      # Analyzes the fetched games```
