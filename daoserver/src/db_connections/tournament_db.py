"""
This file contains code to connect to the tournament_db
"""

import psycopg2

from db_connections.db_connection import db_conn

# pylint: disable=E0602,R0201
class TournamentDBConnection(object):
    """
    Connection class to the tournament database
    """
    @db_conn()
    def get_mission(self, tournament, round_id):
        """Get mission for given round"""
        cur.execute("SELECT mission FROM tournament_round \
                    WHERE tournament_name = %s AND ordering = %s",
                    [tournament, round_id])
        return cur.fetchone()[0]

    @db_conn()
    def get_missions(self, tournament):
        """Get mission for given round"""
        cur.execute("SELECT mission FROM tournament_round \
                    WHERE tournament_name = %s",
                    [tournament])
        return [x[0] for x in cur.fetchall()]

    @db_conn(commit=True)
    def set_mission(self, tournament, round_id, mission):
        """Set mission for given round"""
        cur.execute("SELECT COUNT(*) > 0 FROM tournament_round \
                    WHERE tournament_name = %s AND ordering = %s",
                    [tournament, round_id])
        if cur.fetchone()[0]:
            cur.execute("UPDATE tournament_round SET mission = %s \
                        WHERE tournament_name = %s AND ordering = %s",
                        [mission, tournament, round_id])
        else:
            cur.execute("INSERT INTO tournament_round \
                        VALUES(DEFAULT, %s, %s, %s)",
                        [tournament, round_id, mission])

    @db_conn(commit=True)
    def set_score_key(self, key, category, min_val, max_val):
        """
        Create a score that entries can get in the tournament. This should be
        called for all scores you want, e.g. round_1_battle, round_2_battle

        Expects:
            - a varchar candidate. The key will need to be unique and should
            be a varchar.
            - category - the score_category id
            - min_val. Integer. nin val for the score. Default 0
            - max_val. Integer. max val for the score. Default 20

        Returns: throws ValueError and psycopg2.DatabaseError as appropriate
        """
        if not category or not key:
            raise ValueError('Arguments missing from set_score_category call')
        try:
            min_val = int(min_val)
        except ValueError:
            raise ValueError('Minimum Score must be an integer')

        try:
            max_val = int(max_val)
        except ValueError:
            raise ValueError('Maximum Score must be an integer')

        try:
            cur.execute(
                "INSERT INTO score_key VALUES(default, %s, %s, %s, %s) \
                RETURNING id",
                [key, max_val, min_val, category])
            return cur.fetchone()[0]

        except psycopg2.IntegrityError:
            raise psycopg2.DatabaseError('Score already set')

    @db_conn()
    def get_score_keys_for_round(self, tournament_id, round_id):
        """
        Get all the score keys, and the information from their rows, for a
        particular round
        """
        try:
            round_id = int(round_id)
        except ValueError:
            raise ValueError('Round ID must be an integer')

        cur.execute(
            "SELECT COUNT(*) FROM tournament_round \
            WHERE tournament_name = %s AND ordering = %s",
            [tournament_id, round_id]
        )

        # It may be that the mission has not been set for that round.
        if cur.fetchone()[0] == 0:
            raise ValueError("Draw not ready. Mission not set. Contact TO")
        cur.execute(
            "SELECT * FROM score_key k \
            INNER JOIN round_score s ON s.score_key_id = k.id \
            WHERE s.round_id = %s", [round_id])
        return cur.fetchall()

    @db_conn(commit=True)
    def set_score_key_for_round(self, score_key_id, round_id):
        """
        Attach the score_key to the round. Will then be accessible through
        get_score_keys_for_round
        """
        cur.execute("INSERT INTO round_score VALUES( %s, %s)",
                    [score_key_id, round_id])

