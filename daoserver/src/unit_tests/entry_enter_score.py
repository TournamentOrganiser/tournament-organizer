"""
Test entering scores for games in a tournament
"""

from sqlalchemy.sql.expression import and_
from testfixtures import compare

from models.dao.game_entry import GameEntrant
from models.dao.score import ScoreCategory, TournamentScore, GameScore, \
Score as ScoreDAO
from models.dao.tournament_entry import TournamentEntry
from models.dao.tournament_game import TournamentGame
from models.dao.tournament_round import TournamentRound

from models.score import Score
from models.tournament import Tournament

from unit_tests.app_simulating_test import AppSimulatingTest
from unit_tests.tournament_injector import score_cat_args as cat

# pylint: disable=no-member,missing-docstring
class TestScoreEntered(AppSimulatingTest):
    """Comes from a range of files"""

    tourn_1 = 'score_entered_tournament'

    def setUp(self):
        super(TestScoreEntered, self).setUp()
        self.injector.inject(self.tourn_1, num_players=5)
        tourn = Tournament(self.tourn_1)
        tourn.update({
            'rounds': 2,
            'missions': ['foo_mission_1', 'foo_mission_2']
        })
        tourn.make_draws()

    def test_get_game_from_score(self):
        """
        You should be able to determine game from entry_id and score_category
        """
        entry_2_id = TournamentEntry.query.filter_by(
            player_id='{}_player_{}'.format(self.tourn_1, 2),
            tournament_id=self.tourn_1).first().id
        entry_3_id = TournamentEntry.query.filter_by(
            player_id='{}_player_{}'.format(self.tourn_1, 3),
            tournament_id=self.tourn_1).first().id
        entry_4_id = TournamentEntry.query.filter_by(
            player_id='{}_player_{}'.format(self.tourn_1, 4),
            tournament_id=self.tourn_1).first().id

        # A regular player
        game = self.get_game_by_round(entry_4_id, 1)
        self.assertTrue(game is not None)

        game = self.get_game_by_round(entry_4_id, 1)
        entrants = [x.entrant_id for x in game.entrants.all()]
        compare(len(entrants), 2)
        self.assertTrue(entry_4_id in entrants)
        self.assertTrue(entry_2_id in entrants)

        # A player in a bye
        game = self.get_game_by_round(entry_3_id, 1)
        entrants = [x.entrant_id for x in game.entrants.all()]
        compare(len(entrants), 1)
        self.assertTrue(entry_3_id in entrants)

        # Poor data will return None rather than an error
        game = self.get_game_by_round(15, 1)
        self.assertTrue(game is None)
        game = self.get_game_by_round(1, 12)
        self.assertTrue(game is None)


    def test_no_scores(self):
        """
        There should be an error when you check a game before score categories \
        are assigned to it.
        """
        entry_1_id = TournamentEntry.query.filter_by(
            player_id='{}_player_{}'.format(self.tourn_1, 1),
            tournament_id=self.tourn_1).first().id
        game = self.get_game_by_round(entry_1_id, 1)
        self.assertRaises(AttributeError, Score.is_score_entered, game)


    def test_score_entered(self):
        tourn = Tournament(self.tourn_1)

        score_args = cat('per_round', 50, False, 0, 100)
        cat_1 = ScoreCategory(tournament_id=self.tourn_1, **score_args)
        self.db.session.add(cat_1)
        self.db.session.flush()

        entry_2_id = TournamentEntry.query.filter_by(
            player_id='{}_player_{}'.format(self.tourn_1, 2),
            tournament_id=self.tourn_1).first().id
        entry_3_id = TournamentEntry.query.filter_by(
            player_id='{}_player_{}'.format(self.tourn_1, 3),
            tournament_id=self.tourn_1).first().id
        entry_4_id = TournamentEntry.query.filter_by(
            player_id='{}_player_{}'.format(self.tourn_1, 4),
            tournament_id=self.tourn_1).first().id
        entry_5_id = TournamentEntry.query.filter_by(
            player_id='{}_player_{}'.format(self.tourn_1, 5),
            tournament_id=self.tourn_1).first().id

        # A completed game
        game = self.get_game_by_round(entry_4_id, 1)
        Score(category=cat_1.name, game_id=game.id, tournament=tourn,
              entry_id=entry_2_id, score=2).write()
        Score(category=cat_1.name, game_id=game.id, tournament=tourn,
              entry_id=entry_4_id, score=4).write()
        entrants = [x.entrant_id for x in game.entrants.all()]
        self.assertTrue(entry_2_id in entrants)
        self.assertTrue(entry_4_id in entrants)
        self.assertTrue(Score.is_score_entered(game))

        # A BYE will only have one entrant
        game = self.get_game_by_round(entry_3_id, 1)
        Score(category=cat_1.name, game_id=game.id, tournament=tourn,
              entry_id=entry_3_id, score=3).write()
        entrants = [x.entrant_id for x in game.entrants.all()]
        compare(len(entrants), 1)
        self.assertTrue(entry_3_id in entrants)
        self.assertTrue(Score.is_score_entered(game))

        # Ensure the rd2 game entry_4 vs. entry_5 is listed as not scored. This
        # will force a full check. entry_5's score hasn't been entered.
        game = self.get_game_by_round(entry_4_id, 2)
        game.score_entered = False
        self.db.session.add(game)
        self.db.session.flush()

        game = self.get_game_by_round(entry_4_id, 2)
        entrants = [x.entrant_id for x in game.entrants.all()]
        Score(category=cat_1.name, game_id=game.id, tournament=tourn,
              entry_id=entry_4_id, score=4).write()
        self.assertTrue(entry_4_id in entrants)
        self.assertTrue(entry_5_id in entrants)
        self.assertFalse(Score.is_score_entered(game))

        # Enter the final score for entry_5
        tourn = Tournament(self.tourn_1)
        Score(category=cat_1.name, game_id=game.id, tournament=tourn,
              entry_id=entry_5_id, score=5).write()
        self.assertTrue(Score.is_score_entered(game))

    @staticmethod
    def get_game_by_round(entry_id, round_num):
        """Get the game an entry played in during a round"""
        entry_dao = TournamentEntry.query.filter_by(id=entry_id).first()

        if entry_dao is None:
            return None
        round_dao = TournamentRound.query.filter_by(
            ordering=round_num, tournament_name=entry_dao.tournament.name).\
            first()

        if round_dao is None:
            return None
        return TournamentGame.query.join(GameEntrant).\
            join(TournamentEntry).filter(
                and_(TournamentGame.tournament_round_id == round_dao.id,
                     TournamentEntry.id == entry_id)).first()

class EnterScore(AppSimulatingTest):

    player = 'enter_score_account'
    tourn_1 = 'enter_score_tournament'

    def setUp(self):
        super(EnterScore, self).setUp()
        self.injector.inject(self.tourn_1, num_players=5)
        tourn = Tournament(self.tourn_1)
        tourn.update({
            'rounds': 2,
            'missions': ['foo_mission_1', 'foo_mission_2']
        })
        self.injector.add_player(self.tourn_1, self.player)
        score_args = cat('per_tournament', 50, True, 0, 100)

        # per tournament category
        self.cat_1 = ScoreCategory(tournament_id=self.tourn_1, **score_args)
        self.db.session.add(self.cat_1)

        # per round category
        score_args['name'] = 'per_round'
        score_args['per_tournament'] = False
        self.category_2 = ScoreCategory(tournament_id=self.tourn_1,
                                        **score_args)
        self.db.session.add(self.category_2)
        self.db.session.commit()

    def test_enter_score_bad_games(self):
        """These should all fail for one reason or another"""
        entry = TournamentEntry.query.filter_by(
            player_id=self.player, tournament_id=self.tourn_1).first()

        good_args = {
            'tournament': Tournament(self.tourn_1),
            'entry_id': entry.id,
            'category': self.category_2.name,
            'score': 5
        }
        self.assertRaises(TypeError, Score, game_id='foo', **good_args)
        self.assertRaises(TypeError, Score, game_id=1000000, **good_args)
        self.assertRaises(TypeError, Score, game_id=-1, **good_args)

    def test_enter_score_bad_values(self):
        """These should all fail for one reason or another"""
        entry = TournamentEntry.query.filter_by(
            player_id=self.player, tournament_id=self.tourn_1).first()

        # bad entry
        self.assertRaises(
            ValueError,
            Score,
            tournament=Tournament(self.tourn_1),
            entry_id=10000000,
            category=self.cat_1.name,
            score=5)
        # bad key
        self.assertRaises(
            TypeError,
            Score,
            tournament=Tournament(self.tourn_1),
            entry_id=entry.id,
            category='not_a_key',
            score=5)
        # bad score - character
        self.assertRaises(
            ValueError,
            Score,
            tournament=Tournament(self.tourn_1),
            entry_id=entry.id,
            category=self.cat_1.name,
            score='a')
        # bad score - low
        score = Score(tournament=Tournament(self.tourn_1), entry_id=entry.id,
                      category=self.cat_1.name, score=-1)
        self.assertRaises(ValueError, score.write)
        # bad score - high
        score = Score(tournament=Tournament(self.tourn_1), entry_id=entry.id,
                      category=self.cat_1.name, score=101)
        self.assertRaises(ValueError, score.write)


    def test_enter_score(self):
        """
        Enter a score for an entry
        """
        entry = TournamentEntry.query.filter_by(
            player_id=self.player, tournament_id=self.tourn_1).first()
        tourn = Tournament(self.tourn_1)

        # a one-off score
        Score(category=self.cat_1.name, tournament=tourn, entry_id=entry.id,
              score=0).write()
        scores = TournamentScore.query.\
            filter_by(entry_id=entry.id, tournament_id=tourn.get_dao().id).all()
        compare(len(scores), 1)
        compare(scores[0].score.value, 0)

        # a per_round score
        tourn.make_draws()

        round_id = TournamentRound.query.\
            filter_by(tournament_name=self.tourn_1, ordering=2).first().id
        game_id = TournamentGame.query.join(GameEntrant).\
            filter(and_(GameEntrant.entrant_id == entry.id,
                        TournamentGame.tournament_round_id == round_id)).\
                first().id
        Score(category=self.category_2.name, tournament=tourn, game_id=game_id,
              entry_id=entry.id, score=17).write()
        scores = GameScore.query.\
            filter_by(entry_id=entry.id, game_id=game_id).all()
        compare(len(scores), 1)
        compare(scores[0].score.value, 17)

        # score already entered
        score = Score(tournament=tourn, entry_id=entry.id, score=100,
                      category=self.cat_1.name)
        self.assertRaises(ValueError, score.write)

        score = Score(tournament=tourn, entry_id=entry.id, score=100,
                      category=self.category_2.name, game_id=game_id)
        self.assertRaises(ValueError, score.write)

    def test_enter_score_cleanup(self):
        """make sure no scores are added accidentally"""
        game_scores = len(GameScore.query.all())
        tournament_scores = len(TournamentScore.query.all())
        scores = len(ScoreDAO.query.all())

        self.test_enter_score_bad_games()
        self.test_enter_score_bad_values()

        compare(game_scores, len(GameScore.query.all()))
        compare(tournament_scores, len(TournamentScore.query.all()))
        compare(scores, len(ScoreDAO.query.all()))
