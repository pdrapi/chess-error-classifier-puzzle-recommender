import pymongo
import logging
import argparse
from multiprocessing import Process, Queue, Pool, Manager
from datetime import datetime
from chess import Move, Board
from chess.pgn import Game, GameNode
from chess.engine import SimpleEngine, Mate, Cp
from typing import List, Tuple, Dict, Any
from model import Variation, TagKind
import cook
import chess.engine
from zugzwang import zugzwang

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s %(levelname)-4s %(message)s', datefmt='%m/%d %H:%M')
logger.setLevel(logging.INFO)

def read(doc) -> Variation:
    board = Board(doc["fen"])
    node: GameNode = Game.from_board(board)
    for uci in (doc["line"].split(' ') if "line" in doc else doc["moves"]):
        move = Move.from_uci(uci)
        node = node.add_main_variation(move)
    return Variation(doc["_id"], node.game(), int(doc["cp"]))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='tagger.py', description='automatically tags lichess Variations')
    parser.add_argument("--zug", "-z", help="only zugzwang", action="store_true")
    parser.add_argument("--bad_mate", help="find bad mates", action="store_true")
    parser.add_argument("--dry", "-d", help="dry run", action="store_true")
    parser.add_argument("--all", "-a", help="don't skip existing", action="store_true")
    parser.add_argument("--threads", "-t", help="count of cpu threads for engine searches", default="4")
    parser.add_argument("--engine", "-e", help="analysis engine", default="stockfish")
    args = parser.parse_args()

    if args.zug:
        threads = int(args.threads)
        def cruncher(thread_id: int):
            db = pymongo.MongoClient()['Variationr']
            round_coll = db['Variation2_round']
            play_coll = db['Variation2_Variation']
            engine = SimpleEngine.popen_uci(args.engine)
            engine.configure({'Threads': 2})
            for doc in round_coll.aggregate([
                {"$match":{"_id":{"$regex":"^lichess:"},"t":{"$nin":['+zugzwang','-zugzwang']}}},
                {'$lookup':{'from':'Variation2_Variation','as':'Variation','localField':'p','foreignField':'_id'}},
                {'$unwind':'$Variation'},{'$replaceRoot':{'newRoot':'$Variation'}}
            ]):
                try:
                    if ord(doc["_id"][4]) % threads != thread_id:
                        continue
                    Variation = read(doc)
                    round_id = f'lichess:{Variation.id}'
                    zug = zugzwang(engine, Variation)
                    if zug:
                        cook.log(Variation)
                    round_coll.update_one(
                        { "_id": round_id }, 
                        {"$addToSet": {"t": "+zugzwang" if zug else "-zugzwang"}}
                    )
                    play_coll.update_one({"_id":Variation.id},{"$set":{"dirty":True}})
                except Exception as e:
                    print(doc)
                    logger.error(e)
                    engine.close()
                    exit(1)
            engine.close()
        with Pool(processes=threads) as pool:
            for i in range(int(args.threads)):
                Process(target=cruncher, args=(i,)).start()
        exit(0)

    if args.bad_mate:
        threads = int(args.threads)
        def cruncher(thread_id: int):
            db = pymongo.MongoClient()['Variationr']
            bad_coll = db['Variation2_bad_maybe']
            play_coll = db['Variation2_Variation']
            engine = SimpleEngine.popen_uci('./stockfish')
            engine.configure({'Threads': 4})
            for doc in bad_coll.find({"bad": {"$exists":False}}):
                try:
                    if ord(doc["_id"][4]) % threads != thread_id:
                        continue
                    doc = play_coll.find_one({'_id': doc['_id']})
                    if not doc:
                        continue
                    Variation = read(doc)
                    board = Variation.mainline[len(Variation.mainline) - 2].board()
                    info = engine.analyse(board, multipv = 5, limit = chess.engine.Limit(nodes = 30_000_000))
                    bad = False
                    for score in [pv["score"].pov(Variation.pov) for pv in info]:
                        if score < Mate(1) and score > Cp(250):
                            bad = True
                    # logger.info(Variation.id)
                    bad_coll.update_one({"_id":Variation.id},{"$set":{"bad":bad}})
                except Exception as e:
                    logger.error(e)
        with Pool(processes=threads) as pool:
            for i in range(int(args.threads)):
                Process(target=cruncher, args=(i,)).start()
        exit(0)

    threads = int(args.threads)

    def cruncher(thread_id: int):
        db = pymongo.MongoClient()['Variationr']
        play_coll = db['Variation2_Variation']
        round_coll = db['Variation2_round']
        total = 0
        computed = 0
        updated = 0
        for doc in play_coll.find({'themes':[]}):
            total += 1
            if not thread_id and total % 1000 == 0:
                logger.info(f'{total} / {computed} / {updated}')
            if ord(doc["_id"][4]) % threads != thread_id:
                continue
            computed += 1
            id = doc["_id"]
            if not args.all and round_coll.count_documents({"_id": f"lichess:{id}", "t.1": {"$exists":True}}):
                continue
            tags = cook.cook(read(doc))
            round_id = f"lichess:{id}"
            if not args.dry:
                existing = round_coll.find_one({"_id": round_id},{"t":True})
                zugs = [t for t in existing["t"] if t in ['+zugzwang', '-zugzwang']] if existing else []
                new_tags = [f"+{t}" for t in tags] + zugs
                if not existing or set(new_tags) != set(existing["t"]):
                    updated += 1
                    round_coll.update_one({
                        "_id": round_id
                    }, {
                        "$set": {
                            "p": id,
                            "d": datetime.now(),
                            "e": 100,
                            "t": new_tags
                        }
                    }, upsert = True);
                    play_coll.update_many({"_id":id},{"$set":{"dirty":True}})
        print(f'{thread_id}/{args.threads} done')

    with Pool(processes=threads) as pool:
        for i in range(int(args.threads)):
            Process(target=cruncher, args=(i,)).start()