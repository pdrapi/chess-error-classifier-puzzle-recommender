
import berserk
import chess.pgn
import chess.engine
import cook
import model
import io



class Player:
    def __init__(self, username, api_token):
        #Attributes
        self.api_token = api_token
        self.username = username
        self.session = berserk.TokenSession(api_token)
        self.client = berserk.Client(session=self.session)
        self.profile = None
        self.games = []
        self.analysis_results = []

        # Fetch information about the player
        self.fetch_player_info()


    def fetch_player_info(self):
        """Fetches the player's profile and recent games, filtering for games with evaluations."""
        # Fetch and store the player's profile
        self.profile = self.client.users.get_public_data(self.username)

        # Fetch up to 30 of the player's most recent games that include evaluations
        self.games = list(self.client.games.export_by_player(
            self.username, 
            max=30, 
            evals=True, 
            opening=True, 
            analysed=True ,
            pgn_in_json=True,
            tags=True,
            sort='dateDesc'
        ))
    

    def analyse_mistakes(self):
        for game_data in self.games:
            if 'analysis' not in game_data:
                continue

            game_id = game_data['id']
            pgn = io.StringIO(game_data['pgn'])
            game = chess.pgn.read_game(pgn)
            root_node = game

            for idx, analysis in enumerate(game_data['analysis']):
                if 'judgment' in analysis:
                    move_variations = analysis.get('variation', '').split()
                    eval_score = analysis.get('eval', 0)
                    
                    # Navigate to the current analysis node
                    current_node = root_node
                    for _ in range(idx):
                        if current_node.variations:
                            current_node = current_node.variations[0]

                    # Add all variations from the analysis to the node
                    for san in move_variations:
                        move = current_node.board().parse_san(san)
                        current_node = current_node.add_variation(move)

                    # Using current node throws errors
                    variation_instance = model.Variation(
                        id=f"{game_id}#{idx}",
                        game=game,  
                        cp=eval_score
                    )
                    tags = cook.cook(variation_instance)

                    self.analysis_results.append({
                        'move_number': idx,
                        'variation_id': f"{game_id}#{idx}",
                        'move': move_variations[0] if move_variations else 'N/A',
                        'tags': tags,
                        'comment': analysis['judgment'].get('comment', ''),
                        'color': 'white' if current_node.board().turn else 'black'
                    })

        print("Analysis completed. Total analyses:", len(self.analysis_results))
        return self.analysis_results
    


    def get_analysis_results(self):
        print(self.analysis_results)

api_token = 'lip_PoMsbkUb8ldxVwtiDmhE'
username = 'drapi'
player = Player(username, api_token)
player.analyse_mistakes()
player.get_analysis_results()


    