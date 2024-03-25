import csv
from chess import pgn
import os
from tqdm import tqdm
import sys

def extract_evaluations_and_moves(game):
    moves_and_evals = []
    node = game
    move_number = 1
    while node.variations:
        next_node = node.variation(0)
        if node.board().turn: 
            moves_and_evals.append(f"{move_number}.")
        move_san = node.board().san(next_node.move)
        eval_comment = next_node.comment
        move_and_eval = f"{move_san} {eval_comment}" if eval_comment else move_san
        moves_and_evals.append(move_and_eval)
        if not node.board().turn:  
            move_number += 1
        node = next_node
    return ' '.join(moves_and_evals)


def read_pgn_file(file_path):
    games_with_evaluations = []
    # Estimates the number of games, where each game has 1000 bytes on average
    estimated_total_games = os.path.getsize(file_path) // 1000
    with open(file_path) as pgn_file:
        for _ in tqdm(range(estimated_total_games), desc="Processing games"):
            game = pgn.read_game(pgn_file)
            if game is None:
                break
            game_text = str(game)
            if '{' in game_text: 
                games_with_evaluations.append(game)
    return games_with_evaluations

def extract_game_info(game):
    # Extracts game info from each game in the PGN file
    game_info = {
        'event': game.headers.get('Event', ''),
        'site': game.headers.get('Site', ''),
        'date': game.headers.get('UTCDate', ''),
        'time': game.headers.get('UTCTime', ''),
        'white': game.headers.get('White', ''),
        'black': game.headers.get('Black', ''),
        'result': game.headers.get('Result', ''),
        'whiteElo': game.headers.get('WhiteElo', ''),
        'blackElo': game.headers.get('BlackElo', ''),
        'whiteRatingDiff': game.headers.get('WhiteRatingDiff', ''),
        'blackRatingDiff': game.headers.get('BlackRatingDiff', ''),
        'eco': game.headers.get('ECO', ''),
        'opening': game.headers.get('Opening', ''),
        'timeControl': game.headers.get('TimeControl', ''),
        'termination': game.headers.get('Termination', ''),
        'moves': extract_evaluations_and_moves(game) 
    }
    return game_info


def save_games_to_csv(games, csv_file_path):
    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as csv_file:
        fieldnames = ['event', 'site', 'date', 'time', 'white', 'black', 'result', 'whiteElo', 'blackElo', 'whiteRatingDiff', 'blackRatingDiff', 'whiteTitle', 'eco', 'opening', 'timeControl', 'termination', 'moves']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for game in games:
            game_info = extract_game_info(game)
            writer.writerow(game_info)
    print("Created a new CSV file.")   



def main():
    print("Starting the script...")
    file_path = 'lichess_2014-07.pgn'
    csv_file_path = 'lichess_2014-07.csv'
    print("Reading PGN file...")
    games_with_evaluations = read_pgn_file(file_path)
    print("Saving games to CSV...")
    save_games_to_csv(games_with_evaluations, csv_file_path)
    print("Sucessfully parsed PGN and created a new CSV file. Exiting now.")
    sys.exit()

if __name__ == '__main__':
    main()
