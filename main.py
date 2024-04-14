import berserk
import chess.pgn
import chess.engine
from collections import defaultdict

class Player:
    def __init__(self, api_token, username, engine_path=None):
        """
        Initializes a Player object.

        Parameters:
        - api_token (str): The API token for the player.
        - username (str): The username of the player.
        - engine_path (str, optional): The path to the chess engine executable. Defaults to None.
        """
        #Attributes
        self.api_token = api_token
        self.username = username
        self.session = berserk.TokenSession(api_token)
        self.client = berserk.Client(session=self.session)
        self.profile = None
        self.games = []
        self.analysis_results = []
        self.engine_path = engine_path


        # Fetch information about the player
        self.fetch_player_info()


    def fetch_player_info(self):
        """
        Fetches the player's profile and recent games, filtering for games with evaluations.
        """
        # Fetch and store the player's profile
        self.profile = self.client.users.get_public_data(self.username)

        # Fetch up to 30 of the player's most recent games that include evaluations
        self.games = list(self.client.games.export_by_player(
            self.username, 
            max=30, 
            evals=True, 
            opening=True, 
            analysed=True  
        ))

    def display_info(self):
        """
        Displays information about the player.
        """
        print(f"Username: {self.profile['username']}")
        print(f"Title: {self.profile.get('title', 'N/A')}")

        # Display ratings for each available game type
        for game_type, perf in self.profile.get('perfs', {}).items():
            print(f"{game_type.title()} Rating: {perf['rating']}")

        # Display number of recent games fetched
        print(f"Number of recent games fetched: {len(self.games)}")

    def analyze_games(self):
        """
        Analyzes the player's games and displays the analysis results.
        """
        for game in self.games:
            analysis = GameAnalysis(game, self.username, self.engine_path)
            game_analysis_result = analysis.analyze_game()
            if game_analysis_result is not None:
                self.analysis_results.append([game["id"],game_analysis_result])
        self.analyze_mistakes_aggregate()
        self.display_aggregate_analysis_results()


    def display_analysis_results(self):
        """
        Displays the analysis results for each game.
        """
        for result in self.analysis_results:
            print(f"Game ID: {result[0]}, Mistakes: {result[1]}")
            # Expand this method to display more detailed analysis results
    
    def analyze_mistakes_aggregate(self):
        """
        Aggregates the types of mistakes and associated themes from analysis results.
        """
        mistake_counts = defaultdict(int) 
        theme_counts = defaultdict(lambda: defaultdict(int)) 

        # Iterate through each game's analysis results
        for _, errors in self.analysis_results:
            for error in errors:
                mistake_type = error['type']
                mistake_counts[mistake_type] += 1  

                # Increment theme counts for this mistake type
                for theme in error['themes']:
                    theme_counts[mistake_type][theme] += 1

        # Store the aggregate results in the player object for later use or display
        self.mistake_counts = mistake_counts
        self.theme_counts = theme_counts

    def display_aggregate_analysis_results(self):
        """
        Displays the aggregated analysis results of mistakes and themes.
        """
         # Sorting mistakes by count, in descending order
        for mistake, count in sorted(self.mistake_counts.items(), key=lambda item: item[1], reverse=True):
            print(f"{mistake}: {count}")

        print("\nAggregate Theme Counts by Mistake Type (sorted):")
        # Sorting themes within each mistake type by count, in descending order
        for mistake, themes in sorted(self.theme_counts.items(), key=lambda item: sum(item[1].values()), reverse=True):
            print(f"{mistake}:")
            for theme, count in sorted(themes.items(), key=lambda item: item[1], reverse=True):
                print(f"  {theme}: {count}")

  

class GameAnalysis:
    """
    Class for analyzing chess games.
    """

    def __init__(self, game, username, engine_path=None):
        """
        Initializes a GameAnalysis object.

        Args:
            game (dict): The game data.
            username (str): The username of the player.
            engine_path (str, optional): The path to the chess engine. Defaults to None.
        """
        self.game = game
        self.username = username
        self.engine_path = engine_path
        self.main_board = chess.Board()
        self.variation_board = chess.Board()
        self.side = None
        self.moves = game['moves'].split()
        self.evaluations = self.game['analysis']
        self.errors = []
        self.move_number = 0
        self.material_count = 0
        self.variation = []
        self.opening = None
        self.piece_counts = self.calculate_piece_counts()
        self.piece_values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0
        }

    def analyze_game(self):
        """
        Analyzes the game and returns any errors found during analysis.

        Returns:
            list: The list of errors found during analysis.
        """
        self.check_side()
        if self.find_errors():
            return self.errors
        else:
            print(f"Game {self.game['id']} has no evaluation data.")

    def find_errors(self):
        """
        Finds errors in the game analysis and adds them to the errors list.

        Returns:
            bool: True if errors were found, False otherwise.
        """
        start_index = 0 if self.side == chess.WHITE else 1

        for move_number, (move, eval_dict) in enumerate(zip(self.moves[start_index::2], self.evaluations[start_index::2]), start=1):
            actual_move_number = move_number * 2 - (1 if self.side == chess.WHITE else 0)

            if 'judgment' in eval_dict:
                self.move_number = actual_move_number
                themes = self.analyze_variation_themes(self.move_number, eval_dict.get('variation', ''))
                error = {
                    'move_number': self.move_number,
                    'move': move,
                    'evaluation': eval_dict.get('eval', 'N/A'),
                    'type': eval_dict['judgment']['name'],
                    'themes': themes,
                    'variation': eval_dict.get('variation', '')
                }
                self.errors.append(error)
        return True


    def analyze_variation_themes(self, move_number, variation):
        """
        Check for various conditions within the variation.
        Returns a list of condition names that are true.
        """
        # Ensure the variation board matches the main board state at the beginning of the variation
        self.get_board_state(move_number-1, "main")
        self.get_board_state(move_number-1, "variation")
        self.variation = variation.split()

        themes = []

        # List of condition methods to check
        themes_checks = [
            self.game_phase,
            self.is_promotion,
            self.is_castling,
            self.is_master,
            self.is_pawnEndgame,
            self.is_mate,
            self.is_mate_in,
            self.is_opening,
            self.is_queenEndgame,
            self.is_queenRookEndgame,
            self.is_rookEndgame,
            self.is_bishopEndgame,
            self.is_knightEndgame,
            self.is_advancedPawn,
            self.is_advantage,
            self.is_attackingf2f7,
            self.is_backRankMate,
            self.is_enPassant,
            self.variation_length,
            #self.is_capturingDefender,
            self.is_hangingPiece,
            self.is_doubleCheck,
            self.is_pin
        ]

        for theme_check in themes_checks:
            result = theme_check()
            if result:
                themes.append(result)
            # Reset the board state to the main board's current state after each check
            self.get_board_state(move_number-1, "variation")
            self.calculate_material()

        return themes   
    
    def get_board_state(self, move_number, board_type):
        """
        Retrieves the state of the board at a specific move number.

        Args:
            move_number (int): The move number to retrieve the board state for.
            board_type (str): The type of board to retrieve the state from. Can be "main" or "variation".

        Returns:
            chess.Board: The state of the board at the specified move number.

        Raises:
            ValueError: If the move number is invalid or if an invalid or illegal move is encountered.
        """
        board = self.main_board if board_type == "main" else self.variation_board
        board.reset()
        
        # Check if the specified move number is within the valid range
        if move_number < 1 or move_number > len(self.moves):
            raise ValueError("Invalid move number.")

        # Go through the moves up to the specified move number and apply them to the selected board
        for san in self.moves[:move_number]:
            try:
                move = board.parse_san(san)
                board.push(move)
            except ValueError:
                raise ValueError(f"Invalid move encountered: {san}")
            except chess.IllegalMoveError:
                raise ValueError(f"Illegal move attempted: {san} in board state {board.fen()}")


    def calculate_piece_counts(self):
        """Calculate and return the count of each piece type for both colors."""
        return {
        chess.WHITE: {
            piece_type: len(self.variation_board.pieces(piece_type, chess.WHITE))
            for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]
        },
        chess.BLACK: {
            piece_type: len(self.variation_board.pieces(piece_type, chess.BLACK))
            for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]
        }
    }
    
    def calculate_material(self):
        """
        Calculates the material value for both white and black players.

        The material value is calculated by multiplying the number of each piece type
        by its corresponding value and summing them up for each player.

        Returns:
            None
        """
        self.piece_counts = self.calculate_piece_counts()
        
        # Calculate material for white and black using piece_counts
        self.white_material = sum(self.piece_counts[chess.WHITE][piece_type] * self.piece_values[piece_type] 
                                for piece_type in self.piece_counts[chess.WHITE])
        self.black_material = sum(self.piece_counts[chess.BLACK][piece_type] * self.piece_values[piece_type] 
                                for piece_type in self.piece_counts[chess.BLACK])

        self.material_count = self.white_material + self.black_material

    
    def check_side(self):
        """
        Checks if the analyzed player is white or black based on their username.

        If the analyzed player's username matches the username of the white player in the game,
        the side attribute is set to chess.WHITE. If the analyzed player's username matches the
        username of the black player in the game, the side attribute is set to chess.BLACK.

        Raises:
            ValueError: If the analyzed player is not in the game.

        """
        if self.game["players"]["white"]["user"]["name"] == self.username:
            self.side = chess.WHITE
        elif self.game["players"]["black"]["user"]["name"] == self.username:
            self.side = chess.BLACK
        else:
            raise ValueError("Player is not in the game.")
    
        
    def is_mate(self):
        """
        Checks if the current move results in a checkmate.

        Returns:
            False if the move does not result in a checkmate.
            'mate' if the move results in a checkmate.
        """
        if 'mate' not in self.evaluations[self.move_number-2]:
            return False
        else:
            return 'mate'
    

    def is_mate_in(self):
        """
        Determines if the current position is a checkmate and returns the number of moves until checkmate.

        Returns:
            str: The number of moves until checkmate. Possible values are "mateIn1", "mateIn2", "mateIn3", "mateIn4", or "mateIn5".
        """
        if self.is_mate() == 'mate':
            if self.evaluations[self.move_number-2]['mate'] == 1:
                return "mateIn1"
            elif self.evaluations[self.move_number-2]['mate'] == 2:
                return "mateIn2"
            elif self.evaluations[self.move_number-2]['mate'] == 3:
                return "mateIn3"
            elif self.evaluations[self.move_number-2]['mate'] == 4:
                return "mateIn4"
            elif self.evaluations[self.move_number-2]['mate'] >= 5:
                return "mateIn5"

    def game_phase(self):
        """
        Determines the current phase of the game based on the move number and material count.

        Returns:
            str: The phase of the game, which can be "opening", "middlegame", or "endgame".
        """
        self.calculate_material()

        if self.move_number <= 20:
            return "opening"
        elif 20 < self.move_number < 60 and self.material_count > 35:
            return "middlegame"
        else:
            return "endgame"

    
    def is_opening(self):
        """
        Checks if the game is in the opening phase and returns the name of the opening.

        Returns:
            str: The name of the opening if the game is in the opening phase and an opening is specified, None otherwise.
        """
        if self.game_phase() == "opening" and self.game["opening"] is not None:
            self.opening = self.game["opening"]["name"]
            return self.opening

    def is_castling(self):
        """
        Checks if the current move in the variation is a castling move.

        Returns:
            - "castling" if the move is a castling move.
            - False if the move is not a castling move.

        """
        for san in self.variation:
            move = self.variation_board.parse_san(san)
            if self.variation_board.is_castling(move):
                return "castling"
            self.variation_board.push(move)
        return False
        
    
    def is_master(self):
        """
        Determines the master status of the game.

        Returns:
            str: The master status of the game. Possible values are:
                - "mastervsMaster" if both players have a title.
                - "master" if only one player has a title.
        """
        # Possible bug - to check
        white_title = self.game["players"]["white"].get("title")
        black_title = self.game["players"]["black"].get("title")
        if white_title and black_title:
            return "mastervsMaster"
        elif white_title is not None or black_title is not None:
            return "master"

    def is_pawnEndgame(self):

        # Calculate total non-pawn, non-king pieces for both colors
        non_pawn_pieces = sum(
            sum(self.piece_counts[color][piece] for piece in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN])
            for color in [chess.WHITE, chess.BLACK]
        )
        return "pawnEndgame" if non_pawn_pieces == 0 else False

    def is_queenEndgame(self):
        # Check if there are no knights, bishops, or rooks for both colors, and at least one queen exists
        if all(self.piece_counts[color][piece] == 0 for color in [chess.WHITE, chess.BLACK] for piece in [chess.KNIGHT, chess.BISHOP, chess.ROOK]) \
        and any(self.piece_counts[color][chess.QUEEN] > 0 for color in [chess.WHITE, chess.BLACK]):
            return "queenEndgame"
        return False

    def is_queenRookEndgame(self):
        # Check if there are no knights or bishops for both colors, and at least one queen and one rook exist
        if all(self.piece_counts[color][piece] == 0 for color in [chess.WHITE, chess.BLACK] for piece in [chess.KNIGHT, chess.BISHOP]):
            if any(self.piece_counts[color][chess.QUEEN] > 0 and self.piece_counts[color][chess.ROOK] > 0 for color in [chess.WHITE, chess.BLACK]):
                return "queenRookEndgame"
        return False

    def is_rookEndgame(self):
        # Check if there are no knights, bishops, or queens for both colors, and at least one rook exists
        if all(self.piece_counts[color][piece] == 0 for color in [chess.WHITE, chess.BLACK] for piece in [chess.KNIGHT, chess.BISHOP, chess.QUEEN]):
            if any(self.piece_counts[color][chess.ROOK] > 0 for color in [chess.WHITE, chess.BLACK]):
                return "rookEndgame"
        return False

    def is_knightEndgame(self):
        # Check if there are no bishops, rooks, or queens for both colors, and at least one knight exists
        if all(self.piece_counts[color][piece] == 0 for color in [chess.WHITE, chess.BLACK] for piece in [chess.BISHOP, chess.ROOK, chess.QUEEN]):
            if any(self.piece_counts[color][chess.KNIGHT] > 0 for color in [chess.WHITE, chess.BLACK]):
                return "knightEndgame"
        return False

    def is_bishopEndgame(self):
        # Check if there are no knights, rooks, or queens for both colors, and at least one bishop exists
        if all(self.piece_counts[color][piece] == 0 for color in [chess.WHITE, chess.BLACK] for piece in [chess.KNIGHT, chess.ROOK, chess.QUEEN]):
            if any(self.piece_counts[color][chess.BISHOP] > 0 for color in [chess.WHITE, chess.BLACK]):
                return "bishopEndgame"
        return False


    
    def is_promotion(self):
        for san in self.variation:
            move = self.variation_board.push_san(san)
            if move.promotion is not None and move.promotion != chess.QUEEN:
                return "underpromotion"
            elif move.promotion is not None:
                return "promotion"
        return False
    
    def is_advancedPawn(self):
        """
        Check if any pawn move in the variation is an advancedpawn move.
        """
        for san in self.variation:
            move = self.variation_board.parse_san(san)
            piece = self.variation_board.piece_at(move.from_square)
            if piece and piece.piece_type == chess.PAWN:
                if (self.side == 'white' and piece.color == chess.WHITE and chess.square_rank(move.to_square) in [6, 7, 8]) or \
                (self.side == 'black' and piece.color == chess.BLACK and chess.square_rank(move.to_square) in [1, 2, 3]): 
                    return "advancedPawn"
            self.variation_board.push(move)
        return False
    
    def is_advantage(self):
        """
        Check if the evaluation indicates a significant advantage for one side.
        """
        # there is some offeset in the numbering, -2 eval gets eval and the move of the opponent before our move
        eval = self.evaluations[self.move_number-2].get('eval')
        mistake = self.evaluations[self.move_number-2].get('judgment')

        if eval is not None and mistake is not None:
            if 200 < abs(eval) < 600:
                return "advantage"
            elif abs(eval) > 600 and abs(eval) < 1000:
                return "crushing"
            elif abs(eval) < 200:
                return "equality"
        return False
            
        

    def is_attackingf2f7(self):
        """
        Check if the variation includes an attack on f2/f7 square.
        """
        for san in self.variation:
            move = self.variation_board.parse_san(san)
            if move.to_square in [chess.F2, chess.F7] and self.variation_board.is_capture(move):
                return "attackingf2f7"
            self.variation_board.push(move)
        return False
    
    def is_backRankMate(self):
        """
        Checks if the current variation results in a back rank mate.

        Returns:
            - False if the variation does not result in a checkmate.
            - "backRankMate" if the variation results in a back rank mate.
        """
        for san in self.variation:
            move = self.variation_board.parse_san(san)
            self.variation_board.push(move)

        if not self.variation_board.is_checkmate():
            return False

        # Find the king's position and check if it's on the back rank
        king_color = not self.variation_board.turn
        king_square = self.variation_board.king(king_color)

        if king_color == chess.WHITE and chess.square_rank(king_square) != 1:
            return False
        elif king_color == chess.BLACK and chess.square_rank(king_square) != 8:
            return False
        
        # Calculate the squares directly in front of the king
        direction_offsets = [-1, 0, 1]  
        front_squares = [king_square + offset + (8 if king_color == chess.BLACK else -8) for offset in direction_offsets]

        # Check if all the squares directly in front of the king are blocked by his own pieces
        all_blocked = True
        for square in front_squares:
            if (chess.square_file(square) < 1 or chess.square_file(square) > 8):
                continue  
            piece = self.variation_board.piece_at(square)
            if not piece or piece.color != king_color:
                all_blocked = False
                break

        if all_blocked:
            return "backRankMate"
        return False
    
    def is_enPassant(self):
        """
        Check if the variation includes an en passant move.
        """
        for san in self.variation:
            move = self.variation_board.parse_san(san)
            if self.variation_board.is_en_passant(move):
                return "enPassant"
            self.variation_board.push(move)
        return False
    
    def variation_length(self):
        """
        Determines the length category of the variation.

        Returns:
            str: The length category of the variation. Possible values are:
                - "oneMove" for variations with 1 or 2 moves.
                - "short" for variations with 3 or 4 moves.
                - "long" for variations with 5 or 6 moves.
                - "veryLong" for variations with more than 6 moves.
        """
        if len(self.variation) <= 2:
            return "oneMove"
        elif len(self.variation) <= 4:
            return "short"
        elif len(self.variation) > 4 and len(self.variation) <= 6:
            return "long"
        else:
            return "veryLong"
        
    
    def evaluate_position(self, board):
        """
        Evaluates the given chess board position.

        Args:
            board (chess.Board or str): The chess board position to evaluate. If a string is provided, it will be returned as is.

        Returns:
            int or str: The evaluation score of the position. If the board is a string, it will be returned as is.

        Raises:
            None

        """
        if isinstance(board, str):
            return board
        try:
            engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            result = engine.analyse(board, chess.engine.Limit(depth=20))
            score = result['score'].pov(chess.WHITE)
            cp = score.score(mate_score=10000)
            return cp
        finally:
            engine.quit()
            
    def is_defended(self, square):
        piece = self.variation_board.piece_at(square)
        if piece is None:
            return False

        return self.variation_board.is_attacked_by(piece.color, square)
    
    def is_hanging(self, square):
        return not self.is_defended(square)

    
    def is_hangingPiece(self):
        
        init_material_diff = abs(self.white_material - self.black_material)

        if len(self.variation) < 4:
            for san in self.variation:
                move = self.variation_board.parse_san(san)
                self.variation_board.push(move)
                if self.variation_board.is_capture(move):
                    target_square = move.to_square
                    target = self.variation_board.piece_at(target_square)
                    self.variation_board.pop()
                    if target and target.piece_type != chess.PAWN and self.is_hanging(target_square):
                        self.variation_board.push(move)
                        self.calculate_material()
                        final_material_diff = abs(self.white_material - self.black_material)
                        if final_material_diff > init_material_diff:
                            return "hangingPiece"
                                       
                    else:
                        self.variation_board.push(move) 
        return False

    def is_capturingDefender(self):

        ## DOES NOT WORK PROPERLY - TO BE FIXED

        for san in self.variation:
            move = self.main_board.parse_san(san)
            if self.main_board.is_capture(move):
                defender = self.main_board.piece_at(move.to_square)
                defender_square = move.to_square
                break
            self.main_board.push(move)

        prev_move = None

        if len(self.variation) <= 8:
            for san in self.variation:
                move = self.variation_board.parse_san(san)

                if prev_move and self.variation_board.is_capture(move) and move.to_square != prev_move.to_square:
                    target_square = move.to_square
                    moved_piece = self.variation_board.piece_at(move.from_square)  # Get the piece that moved
                    target_piece = self.main_board.piece_at(target_square)
                    self.variation_board.push(move)

                    # Evaluate conditions for a capturing defender
                    if target_piece and moved_piece and moved_piece.piece_type != chess.KING \
                            and self.piece_values[moved_piece.piece_type] >= self.piece_values[target_piece.piece_type] \
                            and self.is_hanging(target_square):
                        if defender and defender_square in self.main_board.attackers(defender.color, target_square) \
                                and not self.main_board.is_check():
                            return True
                else:
                    # This push is only necessary if the above condition is not met
                    self.variation_board.push(move)
                    
                prev_move = move  # Update the previous move

        return False
        
    def is_discoveredcheck(self):
        for san in self.variation:
            move = self.variation_board.parse_san(san)
            checkers = self.variation_board.checkers()
            if checkers and move.to_square not in checkers:
                return True
            self.variation_board.push(move)
        return False
    
    ## NOT DONE
    def is_discoveredAttack(self):
        if self.is_discoveredcheck():
            return True
        for idx, san in enumerate(self.variation, start=1):
            move = self.variation_board.parse_san(san)
            if idx % 2 == 1:
                attackers = self.variation_board.attackers(not self.variation_board.turn, move.to_square)
                between = chess.SquareSet(chess.between(move.from_square, move.to_square))

            self.variation_board.push(move)
        return False
    
    def is_doubleCheck(self):
        for san in self.variation:
            move = self.variation_board.parse_san(san)
            if len(self.variation_board.checkers()) > 1:
                return "doubleCheck"
            self.variation_board.push(move)
        return False
    
    def is_pin(self):
        """
        Check if any piece on the board is pinned in such a way that moving it would expose a higher value piece or the king.
        """
        # has some false positives for now
        if self.side == chess.WHITE:
            color = chess.BLACK
        else:
            color = chess.WHITE

        for san in self.variation:
            move = self.variation_board.parse_san(san)
            attacker_square = move.to_square
            attacked_squares = self.variation_board.attacks(attacker_square)
            for square in attacked_squares:
                attacked_piece = self.variation_board.piece_at(square)
                if self.variation_board.is_pinned(color, square):
                    return "pin"
                elif attacked_piece and attacked_piece.piece_type != chess.KING:
                    if self.variation_board.remove_piece_at(square):
                        new_attacked_squares = self.variation_board.attacks(attacker_square)
                        for new_square in new_attacked_squares:
                            for attacked_square in attacked_squares:
                                if new_square != attacked_square:
                                    defended_piece = self.variation_board.piece_at(new_square) 
                                    if defended_piece and self.piece_values[defended_piece.piece_type] > self.piece_values[attacked_piece.piece_type]:
                                        return "pin"
                    return False
            self.variation_board.push(move)                         
                   
        return False


        


    
