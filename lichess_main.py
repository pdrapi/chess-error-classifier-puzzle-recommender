import chess
import chess.engine
import asyncio

'''
1. Think whether to use API or just the database
2. Create a list of first top 10 categories that are the easiest to map, then the next.
3. Figure out how to map using FEN probably
'''
def get_board_state(moves, move_number):

    # Create a board
    board = chess.Board()
    # Split the moves string into a list of individual moves
    moves = moves.split()

    # Check if in range
    if move_number < 1 or move_number > len(moves):
        return "Invalid move number"

    # Go through moves
    for move_san in moves[:move_number]:
        try:
            move = board.parse_san(move_san) 
            board.push(move)
        except ValueError:
            return "Invalid move encountered"
        
    # Return the FEN string of the current board position
    return board

def get_fen(board):
    return board.fen()


async def evaluate_position(moves, move_number, engine_path):
    board = get_board_state(moves, move_number)
    transport, engine = await chess.engine.popen_uci(engine_path)

    try:
        info = await engine.analyse(board, chess.engine.Limit(time=0.1))
        print("Analysis result:", info)
    finally:
        await engine.quit()


