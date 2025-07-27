import pygame
import sys
import time
import random
import math
import os

def resource_path(relative_path):
    # PyInstaller로 빌드된 exe에서 asset 경로를 자동으로 잡아줌
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# 게임 설정
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 640
FPS = 60
NOTE_SPEED = 8  # 더 빠르게

# 라인 설정
LANE_COUNT = 4
LANE_WIDTH = 80
LANE_X = [60, 160, 260, 360]  # 각 라인의 x좌표 (A, S, D, F)

# 박자/노트 설정
BPM = 80
BEAT_INTERVAL = 60 / BPM
SONG_LENGTH = 115  # 실제 음악 길이(초)로 맞추세요
TICK_DELAY = 200
DELAY_SEC = TICK_DELAY / FPS
JUDGE_OFFSET = 0.12  # 120ms 정도 앞당김

# 판정/게임 시스템 변수
NOTE_START_Y = -20
JUDGE_LINE_Y = 485
NOTE_TRAVEL_TIME = 1.0  # 노트가 내려오는 데 걸리는 시간(초)

# 콤보, HP, 판정 통계
combo = 0
max_combo = 0
hp = 100
score = 0
perfect_count = 0
good_count = 0
bad_count = 0
miss_count = 0

# 파티클 효과
particles = []

# 노트 생성 (80BPM, 무작위 라인, 더블노트 확률)
notes = []
current_time = 0
while current_time < SONG_LENGTH:
    # 1. 80BPM 기본 노트
    lanes = [random.randint(0, LANE_COUNT - 1)]
    # 더블노트 확률 15%
    if random.random() < 0.15:
        other_lane = random.randint(0, LANE_COUNT - 1)
        while other_lane == lanes[0]:
            other_lane = random.randint(0, LANE_COUNT - 1)
        lanes.append(other_lane)
    for lane in lanes:
        notes.append({'time': round(current_time + DELAY_SEC - JUDGE_OFFSET, 2), 'lane': lane, 'surprise': False, 'gen_time': current_time})

    # 2. 40BPM 서프라이즈 노트 (80BPM의 중간 박자, 확률적으로 등장)
    surprise_time = current_time + BEAT_INTERVAL / 2
    if surprise_time < SONG_LENGTH + NOTE_TRAVEL_TIME and random.random() < 0.3:  # 30% 확률
        surprise_lane = random.randint(0, LANE_COUNT - 1)
        notes.append({'time': round(surprise_time + DELAY_SEC - JUDGE_OFFSET, 2), 'lane': surprise_lane, 'surprise': True, 'gen_time': current_time})

    current_time += BEAT_INTERVAL

# 초기화
pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("굴제이맥스")
clock = pygame.time.Clock()

try:
    bg_img = pygame.image.load(resource_path("background.png"))
except:
    bg_img = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    bg_img.fill((0, 0, 0))
try:
    pygame.mixer.music.load(resource_path("song.mp3"))
except:
    print("음악 파일(song.mp3)이 없습니다. 음악 없이 진행합니다.")
try:
    hit_sound = pygame.mixer.Sound(resource_path("hit.wav"))
except:
    hit_sound = None
try:
    note_img = pygame.image.load(resource_path("note.png"))
except:
    note_img = pygame.Surface((60, 20))
    note_img.fill((255, 0, 0))

judge_text = ""
judge_time = 0

# 노트 클래스
class Note:
    def __init__(self, time, lane, surprise=False, gen_time=0):
        self.time = time
        self.lane = lane
        self.surprise = surprise
        self.y = NOTE_START_Y
        self.hit = False
        self.missed = False
        self.gen_time = gen_time

    def update(self, current_time):
        t = (current_time - (self.time - NOTE_TRAVEL_TIME))
        if t < 0:
            self.y = NOTE_START_Y
        elif t > NOTE_TRAVEL_TIME:
            self.y = JUDGE_LINE_Y
        else:
            self.y = NOTE_START_Y + (JUDGE_LINE_Y - NOTE_START_Y) * (t / NOTE_TRAVEL_TIME)
        # 노트가 처음 등장한 시각 기록
        # if self.spawn_time is None and t >= 0: # 이 부분은 더 이상 사용되지 않음
        #     self.spawn_time = current_time

    def draw(self, surface):
        if not self.hit and not self.missed and self.y <= JUDGE_LINE_Y:
            if hasattr(self, 'hard_green') and self.hard_green:
                color = (0, 255, 0)  # 초록
            elif self.surprise:
                color = (0, 255, 255)  # 파랑
            else:
                color = (255, 0, 0)    # 빨강
            note_img = pygame.Surface((60, 20))
            note_img.fill(color)
            surface.blit(note_img, (LANE_X[self.lane], int(self.y)))

note_objs = [Note(n['time'], n['lane'], n.get('surprise', False), n.get('gen_time', 0)) for n in notes]

start_time = None
running = True

if pygame.mixer.music.get_busy():
    pygame.mixer.music.stop()
try:
    pygame.mixer.music.play()
    start_time = time.time()
except:
    start_time = time.time()
if start_time is None:
    start_time = time.time()

# 키와 라인 매핑
KEY_LANE = {
    pygame.K_a: 0,
    pygame.K_s: 1,
    pygame.K_d: 2,
    pygame.K_f: 3,
}

# 판정 효과 리스트
effects = []

# 파티클 클래스
def spawn_particles(x, y, color):
    for _ in range(15):
        angle = random.uniform(0, 2 * 3.1415)
        speed = random.uniform(2, 6)
        dx = speed * math.cos(angle)
        dy = speed * math.sin(angle)
        particles.append({'x': x, 'y': y, 'dx': dx, 'dy': dy, 'life': random.uniform(0.2, 0.5), 'color': color, 'start': time.time()})

game_over = False
result_time = 0

def draw_button(surface, rect, text, font, color, text_color):
    pygame.draw.rect(surface, color, rect)
    label = font.render(text, True, text_color)
    label_rect = label.get_rect(center=rect.center)
    surface.blit(label, label_rect)


def select_difficulty():
    selecting = True
    font = pygame.font.SysFont(None, 48)
    buttons = [
        ("Easyun", (80, 150, 320, 60)),
        ("Normal", (80, 230, 320, 60)),
        ("Hard", (80, 310, 320, 60)),
        ("Gunddong", (80, 390, 320, 60)),
    ]
    while selecting:
        screen.fill((30, 30, 30))
        title = font.render("Select Difficulty", True, (255,255,255))
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 60))
        for name, rect in buttons:
            pygame.draw.rect(screen, (80,80,200), rect)
            label = font.render(name, True, (255,255,255))
            label_rect = label.get_rect(center=(rect[0]+rect[2]//2, rect[1]+rect[3]//2))
            screen.blit(label, label_rect)
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                for idx, (name, rect) in enumerate(buttons):
                    x, y, w, h = rect
                    if x <= mx <= x+w and y <= my <= y+h:
                        return ["easy", "normal", "hard", "gunddong"][idx]

def generate_notes(difficulty):
    notes = []
    current_time = 0
    if difficulty == "easy":
        while current_time < SONG_LENGTH:
            # 80BPM 기본 노트(빨강)
            lanes = [random.randint(0, LANE_COUNT - 1)]
            for lane in lanes:
                notes.append({'time': round(current_time + DELAY_SEC - JUDGE_OFFSET, 2), 'lane': lane, 'surprise': False, 'gen_time': current_time})
            # 40BPM 파란 노트(확률)
            surprise_time = current_time + BEAT_INTERVAL / 2
            if surprise_time < SONG_LENGTH and random.random() < 0.3:
                surprise_lane = random.randint(0, LANE_COUNT - 1)
                notes.append({'time': round(surprise_time + DELAY_SEC - JUDGE_OFFSET, 2), 'lane': surprise_lane, 'surprise': True, 'gen_time': current_time})
            current_time += BEAT_INTERVAL
    elif difficulty == "normal":
        while current_time < SONG_LENGTH:
            # 80BPM 모두 파란 노트
            lanes = [random.randint(0, LANE_COUNT - 1)]
            for lane in lanes:
                notes.append({'time': round(current_time + DELAY_SEC - JUDGE_OFFSET, 2), 'lane': lane, 'surprise': True, 'gen_time': current_time})
            # 40BPM 파란 노트(확률 높임)
            surprise_time = current_time + BEAT_INTERVAL / 2
            if surprise_time < SONG_LENGTH and random.random() < 0.7:
                surprise_lane = random.randint(0, LANE_COUNT - 1)
                notes.append({'time': round(surprise_time + DELAY_SEC - JUDGE_OFFSET, 2), 'lane': surprise_lane, 'surprise': True, 'gen_time': current_time})
            current_time += BEAT_INTERVAL
    elif difficulty == "hard":
        while current_time < SONG_LENGTH:
            # 80BPM 기본 노트
            lanes = [random.randint(0, LANE_COUNT - 1)]
            for lane in lanes:
                notes.append({'time': round(current_time + DELAY_SEC - JUDGE_OFFSET, 2), 'lane': lane, 'surprise': False, 'gen_time': current_time})
            # 40BPM 파란 노트
            surprise_time = current_time + BEAT_INTERVAL / 2
            if surprise_time < SONG_LENGTH:
                surprise_lane = random.randint(0, LANE_COUNT - 1)
                notes.append({'time': round(surprise_time + DELAY_SEC - JUDGE_OFFSET, 2), 'lane': surprise_lane, 'surprise': True, 'gen_time': current_time})
            # 20BPM(80BPM/4) 초록 노트
            for i in range(1, 4):
                green_time = current_time + BEAT_INTERVAL * i / 4
                if green_time < SONG_LENGTH:
                    green_lane = random.randint(0, LANE_COUNT - 1)
                    notes.append({'time': round(green_time + DELAY_SEC - JUDGE_OFFSET, 2), 'lane': green_lane, 'surprise': False, 'gen_time': green_time, 'hard_green': True})
            current_time += BEAT_INTERVAL
    elif difficulty == "gunddong":
        interval = 0.05  # 0.05초마다 노트 생성 (20개/초)
        current_time = 0
        while current_time < SONG_LENGTH:
            # 한 번에 1~4개 라인에 노트 생성
            lines = random.sample(range(LANE_COUNT), random.randint(1, LANE_COUNT))
            for lane in lines:
                note_type = random.choice(["red", "blue", "green"])
                notes.append({
                    'time': round(current_time + DELAY_SEC - JUDGE_OFFSET, 2),
                    'lane': lane,
                    'surprise': note_type == "blue",
                    'gen_time': current_time,
                    'hard_green': note_type == "green"
                })
            current_time += interval
    return notes


def main():
    global combo, max_combo, hp, score, perfect_count, good_count, bad_count, miss_count, particles, note_objs, start_time, running, game_over, result_time, judge_text, judge_time
    # 변수 초기화
    combo = 0
    max_combo = 0
    hp = 100
    score = 0
    perfect_count = 0
    good_count = 0
    bad_count = 0
    miss_count = 0
    particles = []
    difficulty = select_difficulty()
    notes = generate_notes(difficulty)
    note_objs = [Note(n['time'], n['lane'], n.get('surprise', False), n.get('gen_time', 0)) for n in notes]
    start_time = None
    running = True
    game_over = False
    result_time = 0
    judge_text = ""
    judge_time = 0

    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
    try:
        pygame.mixer.music.play()
        start_time = time.time()
    except:
        start_time = time.time()
    if start_time is None:
        start_time = time.time()

    while running:
        current_time = time.time() - start_time

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and not game_over:
                key_char = event.unicode.lower()
                key_map = {'a': 0, 's': 1, 'd': 2, 'f': 3}
                if key_char in key_map:
                    lane = key_map[key_char]
                    # 판정선 근처 노트만 후보로
                    candidates = [
                        note for note in note_objs
                        if not note.hit and not note.missed and note.lane == lane and abs((note.y + 20//2) - JUDGE_LINE_Y) < 60
                    ]
                    if candidates:
                        note = min(candidates, key=lambda n: abs((n.y + 20//2) - JUDGE_LINE_Y))
                        diff = abs((note.y + 20//2) - JUDGE_LINE_Y)
                        # 이하 판정 로직
                        if diff < 10:
                            judge_text = "Perfect!"
                            score += 300
                            combo += 1
                            perfect_count += 1
                            spawn_particles(LANE_X[lane]+30, JUDGE_LINE_Y, (255,255,0))
                        elif diff < 30:
                            judge_text = "Good!"
                            score += 100
                            combo += 1
                            good_count += 1
                            spawn_particles(LANE_X[lane]+30, JUDGE_LINE_Y, (0,255,0))
                        elif diff < 50:
                            judge_text = "Bad!"
                            score += 10
                            combo += 1
                            bad_count += 1
                            spawn_particles(LANE_X[lane]+30, JUDGE_LINE_Y, (0,128,255))
                        # else: 그냥 아무것도 안 함
                        note.hit = True
                        judge_time = time.time()
                        if hit_sound:
                            hit_sound.play()
                        effects.append({'lane': lane, 'radius': 10, 'start': time.time()})
            if game_over:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    # 종료 버튼
                    if 140 <= mx <= 340 and 400 <= my <= 450:
                        pygame.quit()
                        sys.exit()
                    # 다시 플레이 버튼
                    if 140 <= mx <= 340 and 460 <= my <= 510:
                        return  # main()을 다시 호출

        # 업데이트
        for note in note_objs:
            note.update(current_time)

        for note in note_objs:
            # 파란색(서프라이즈) 노트는 4.0초, 일반 노트는 3.5초
            fail_time = 3.7 if note.surprise else 3.5
            if not note.hit and not note.missed and current_time - note.gen_time >= fail_time:
                note.missed = True
                judge_text = "Fail!"
                combo = 0
                miss_count += 1
                hp -= 10
                judge_time = time.time()
                spawn_particles(LANE_X[note.lane]+30, JUDGE_LINE_Y, (255,0,0))

        # 판정된(맞춘) 노트와 missed 노트 모두 삭제
        note_objs = [note for note in note_objs if not (note.missed or note.hit)]

        max_combo = max(max_combo, combo)
        if (hp <= 0 or current_time > SONG_LENGTH + 5) and not game_over:
            game_over = True
            result_time = time.time()
            pygame.mixer.music.stop()

        # 파티클 업데이트
        for p in particles[:]:
            elapsed = time.time() - p['start']
            if elapsed > p['life']:
                particles.remove(p)
                continue
            p['x'] += p['dx']
            p['y'] += p['dy']
            p['dy'] += 0.3  # 중력 효과

        screen.blit(bg_img, (0, 0))
        # 라인 그리기
        for x in LANE_X:
            pygame.draw.rect(screen, (50, 50, 50), (x, 0, LANE_WIDTH, SCREEN_HEIGHT))
        # 판정선
        pygame.draw.line(screen, (0, 255, 0), (0, JUDGE_LINE_Y), (SCREEN_WIDTH, JUDGE_LINE_Y), 2)

        # 1. 노트 먼저 그리기
        for note in note_objs:
            note.draw(screen)

        # 2. 파티클 그리기 (노트 위에)
        for p in particles:
            pygame.draw.circle(screen, p['color'], (int(p['x']), int(p['y'])), 4)

        # 3. 이펙트 그리기 (판정 원 등)
        for effect in effects[:]:
            elapsed = time.time() - effect['start']
            if elapsed > 0.3:
                effects.remove(effect)
                continue
            alpha = int(255 * (1 - elapsed / 0.3))
            color = (255, 255, 0, alpha)
            surf = pygame.Surface((LANE_WIDTH, LANE_WIDTH), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (LANE_WIDTH//2, LANE_WIDTH//2), int(effect['radius'] + 40*elapsed))
            screen.blit(surf, (LANE_X[effect['lane']], JUDGE_LINE_Y - LANE_WIDTH//2))

        font = pygame.font.SysFont(None, 36)
        score_text = font.render(f"Score: {score}", True, (255, 255, 255))
        combo_text = font.render(f"Combo: {combo}", True, (255, 255, 0))
        hp_text = font.render(f"HP: {hp}", True, (255, 100, 100))
        screen.blit(score_text, (10, 10))
        screen.blit(combo_text, (10, 50))
        screen.blit(hp_text, (10, 90))

        if judge_text and time.time() - judge_time < 1:
            judge_surface = font.render(judge_text, True, (255, 255, 0))
            screen.blit(judge_surface, (SCREEN_WIDTH//2 - 60, 400))
        elif time.time() - judge_time >= 1:
            judge_text = ""

        # 게임 오버/결과 화면
        if game_over:
            result_font = pygame.font.SysFont(None, 48)
            result_text = result_font.render("Game Over!", True, (255, 0, 0))
            screen.blit(result_text, (SCREEN_WIDTH//2 - 120, 200))
            stat_font = pygame.font.SysFont(None, 32)
            stat1 = stat_font.render(f"Score: {score}", True, (255,255,255))
            stat2 = stat_font.render(f"Max Combo: {max_combo}", True, (255,255,0))
            stat3 = stat_font.render(f"Perfect: {perfect_count}  Good: {good_count}  Bad: {bad_count}  Miss: {miss_count}", True, (0,255,255))
            screen.blit(stat1, (SCREEN_WIDTH//2 - 100, 270))
            screen.blit(stat2, (SCREEN_WIDTH//2 - 100, 310))
            screen.blit(stat3, (SCREEN_WIDTH//2 - 180, 350))
            # 버튼
            button_font = pygame.font.SysFont(None, 36)
            quit_rect = pygame.Rect(140, 400, 200, 50)
            retry_rect = pygame.Rect(140, 460, 200, 50)
            draw_button(screen, quit_rect, "Quit", button_font, (200,0,0), (255,255,255))
            draw_button(screen, retry_rect, "I can't believe this result", button_font, (0,200,0), (255,255,255))

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    main()
