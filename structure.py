class QuizMode:
    def __init__(self):
        self.current_song_title = ''
        self.current_song_url = ''
        self.current_song_guessed = False
        self.time_passed = False
        self.size = 30
        self.skips_needed = 1
        self.song_id = 0
        self.skips = 0
        self.skippers = []
        self.points = {}
        self.unavailable = False

    def set_song(self, new_title, new_url):
        self.current_song_title = new_title
        self.current_song_url = new_url
        self.current_song_guessed = False
        self.time_passed = True

    def set_quiz(self, size=30, skips=1):
        self.size = size
        self.skips_needed = skips
        self.song_id = 0
        self.skips = 0
        self.skippers = []
        self.points = {}

    def incr_song_id(self):
        self.song_id += 1
    
    def add_skip(self, username):
        if username not in self.skippers:
            self.skips += 1
            self.skippers.append(username)

    def clear_skips(self):
        self.skips = 0
        self.skippers = []

    def guess_song(self, username):
        if self.points.get(username, 0) == 0:
            self.points[username] = 1
        else:
            self.points[username] += 1

        self.current_song_guessed = True
    
    def show_leaderboard(self):
        leaderboard = ''
        sorted_points = sorted(self.points.items(), key=lambda x: x[1], reverse=True)

        place = 1
        leaderboard += '==========================\n'
        leaderboard += '**GG!**\n'
        for i in sorted_points:
            leaderboard += ('**' + str(place) + '.** ' + str(i[0]) + ': ' + str(i[1]) + '\n')
            place += 1
        leaderboard += '=========================='
        
        return leaderboard



class Status:
    def __init__(self):
        self.mode = 'afk'

        self.queue = []

        self.quiz = QuizMode()

    def change_mode(self, new_mode):
        self.mode = new_mode