"""
Model of a tournament

It holds a tournament object for housing of scoring strategies, etc.
"""
import datetime

from db_connections.entry_db import EntryDBConnection
from db_connections.tournament_db import TournamentDBConnection
from matching_strategy import RoundRobin
from permissions import PermissionsChecker, PERMISSIONS
from ranking_strategies import RankingStrategy
from table_strategy import ProtestAvoidanceStrategy

def must_exist_in_db(func):
    """ A decorator that requires the tournament exists in the db"""
    def wrapped(self, *args, **kwargs):                 # pylint: disable=C0111
        if not self.exists_in_db:
            print 'Tournament not found: {}'.format(self.tournament_id)
            raise ValueError(
                'Tournament {} not found in database'.format(
                    self.tournament_id))
        return func(self, *args, **kwargs)
    return wrapped

class Tournament(object):
    """A tournament DAO"""

    def __init__(self, tournament_id=None, ranking_strategy=None, creator=None):
        self.tourn_db_conn = TournamentDBConnection()
        self.tournament_id = tournament_id
        self.exists_in_db = tournament_id is not None \
            and self.tourn_db_conn.tournament_exists(tournament_id)
        self.ranking_strategy = \
            ranking_strategy(tournament_id, self.list_score_categories) \
            if ranking_strategy \
            else RankingStrategy(tournament_id, self.list_score_categories)
        self.matching_strategy = RoundRobin(tournament_id)
        self.table_strategy = ProtestAvoidanceStrategy()
        self.creator_username = creator

    def add_to_db(self, date):
        """
        add a tournament
        Expects:
            - inputTournamentDate - Tournament Date. YYYY-MM-DD
        """
        if self.exists_in_db:
            raise RuntimeError('A tournament with name {} already exists! \
            Please choose another name'.format(self.tournament_id))

        date = datetime.datetime.strptime(date, "%Y-%m-%d")
        if date.date() < datetime.date.today():
            raise ValueError('Enter a valid date')

        self.tourn_db_conn.add_tournament(
            {'name' : self.tournament_id, 'date' : date})

        PermissionsChecker().add_permission(
            self.creator_username,
            PERMISSIONS['ENTER_SCORE'],
            self.tourn_db_conn.tournament_details(self.tournament_id)[4])

    @must_exist_in_db
    def create_score_category(self, category, percentage):
        """ Add a score category """
        self.tourn_db_conn.create_score_category(
            category, self.tournament_id, percentage)

    @must_exist_in_db
    def details(self):
        """
        Get details about a tournament. This includes entrants and format
        information
        """
        details = self.tourn_db_conn.tournament_details(self.tournament_id)

        return {
            'name': details[1],
            'date': details[2],
            'details': {
                'rounds': details[3] if details[3] is not None else 0,
                'score_format': details[4] if details[4] is not None else 'N/A',
            }
        }

    @must_exist_in_db
    def list_score_categories(self):
        """
        List all the score categories available to this tournie and their
        percentages.
        [{ 'name': 'Painting', 'percentage': 20, 'id': 1 }]
        """
        return self.tourn_db_conn.list_score_categories(self.tournament_id)

    @staticmethod
    def list_tournaments():
        """
        GET a list of tournaments
        Returns json. The only key is 'tournaments' and the value is a list of
        tournament names
        """
        tourn_db_conn = TournamentDBConnection()
        return {'tournaments' : tourn_db_conn.list_tournaments()}

    @must_exist_in_db
    def make_draw(self, round_id=0):
        """Determines the draw for round. This draw is written to the db"""
        match_ups = self.matching_strategy.match(int(round_id))
        draw = self.table_strategy.determine_tables(match_ups)
        try:
            from game import Game
            for match in draw:
                game = Game(match.entrants,
                            tournament_id=self.tournament_id,
                            round_id=round_id,
                            table_number=match.table_number)
                game.write_to_db()
                if game.entry_1 is not None:
                    entry_id = game.entry_1
                    uname = EntryDBConnection().entry_info(entry_id)['username']
                    PermissionsChecker().add_permission(
                        uname,
                        PERMISSIONS['ENTER_SCORE'],
                        game.protected_object_id)
                if game.entry_2 is not None:
                    entry_id = game.entry_2
                    uname = EntryDBConnection().entry_info(entry_id)['username']
                    PermissionsChecker().add_permission(
                        uname,
                        PERMISSIONS['ENTER_SCORE'],
                        game.protected_object_id)

                # The person playing the bye gets no points at the time
                if None in [game.entry_1, game.entry_2]:
                    game.set_score_entered()

        except ValueError as err:
            if 'duplicate key value violates unique constraint "game_pkey"' \
            not in str(err):
                raise err

        return draw

    @must_exist_in_db
    def get_mission(self, round_id):
        """Get the mission for a given round"""
        return self.tourn_db_conn.get_mission(self.tournament_id, round_id)

    @must_exist_in_db
    def get_missions(self):
        """Get all missions for the tournament"""
        return self.tourn_db_conn.get_missions(self.tournament_id)

    @must_exist_in_db
    def round_info(self, round_id=0):
        """
        Returns info about round.
        Returns:
            - dict with three keys {score_keys, draw, mission}
        """
        return {
            'score_keys': self.get_score_keys_for_round(round_id),
            'draw': self.make_draw(round_id),
            'mission': self.get_mission(round_id)
        }

    @must_exist_in_db
    def set_mission(self, round_id, mission):
        """Set the mission for a given round"""
        self.tourn_db_conn.set_mission(self.tournament_id, round_id, mission)

    @must_exist_in_db
    def set_number_of_rounds(self, num_rounds):
        """Set the number of rounds in a tournament"""
        self.tourn_db_conn.set_rounds(self.tournament_id, int(num_rounds))

    @must_exist_in_db
    def set_score(self, key, category, min_val=0, max_val=20, round_id=None):
        """
        Set a score category that a player is eligible for in a tournament.

        For example, use this to specify that a tourn has a 'round_1_battle'
        score for each player.

        Expected:
            - key - unique name e.g. round_4_comp
            - (opt) min_val - for score - default 0
            - (opt) max_val - for score - default 20
            - (opt) round_id - the score is for the round
        """
        if not min_val:
            min_val = 0
        if not max_val:
            max_val = 20

        score_key = self.tourn_db_conn.set_score_key(
            key=key,
            category=category,
            min_val=min_val,
            max_val=max_val)

        if round_id is not None:
            self.tourn_db_conn.set_score_key_for_round(score_key, round_id)

    @must_exist_in_db
    def get_score_keys_for_round(self, round_id='next'):
        """ Get all the score keys associated with this round"""

        #TODO get next round
        if round_id == 'next':
            raise NotImplementedError('next round is unknown')

        return self.tourn_db_conn.get_score_keys_for_round(
            self.tournament_id, round_id)
