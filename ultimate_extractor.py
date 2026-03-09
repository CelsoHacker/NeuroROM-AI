#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ULTIMATE EXTRACTOR - ROM TRANSLATION FRAMEWORK
===============================================

Combina o melhor de todos os métodos:
1. Charsets conhecidos (dual charset) ✅
2. Seguidor de ponteiros ✅
3. Validação expandida ✅
4. Correção de fragmentação ✅
5. Varredura byte-a-byte inteligente ✅
"""

from pathlib import Path
from typing import Dict, List, Tuple, Set
from collections import Counter, defaultdict
import re


class KnownCharsets:
    """Charsets conhecidos e documentados para SNES."""

    # Charset 1: Message Box/Overworld (SMW)
    MESSAGE_CHARSET = {
        **{i: chr(ord('A') + i) for i in range(26)},  # 0x00-0x19 = A-Z
        0x1A: ' ',
        0x1B: '!',
        0x1C: '?',
        0x1D: '.',
        0x1E: ',',
        0x1F: '-',
        0x20: "'",
        0x21: '"',
        0x22: '0', 0x23: '1', 0x24: '2', 0x25: '3', 0x26: '4',
        0x27: '5', 0x28: '6', 0x29: '7', 0x2A: '8', 0x2B: '9',
        **{i + 0x40: chr(ord('a') + i) for i in range(26)},  # 0x40-0x59 = a-z
        0xFE: None,  # Terminador
        0xFF: '\n',
    }

    # Charset 2: Title Screen/Status Bar (SMW)
    TITLE_CHARSET = {
        **{i: str(i) for i in range(10)},  # 0x00-0x09 = 0-9
        **{i + 0x0A: chr(ord('A') + i) for i in range(26)},  # 0x0A-0x23 = A-Z
        0x24: ' ',
        0x25: '-',
        0x26: ',',
        0x27: '.',
        0xFE: None,
    }

    # Charset 3: ASCII Padrão (jogos que usam ASCII)
    ASCII_CHARSET = {
        **{i: chr(i) for i in range(32, 127)},  # Printable ASCII
        0x00: None,  # Terminador
        0x0A: '\n',
        0x0D: '\n',
    }

    # Charset 4: Shift -1 (alguns jogos SNES)
    SHIFT_MINUS_ONE = {
        **{i + 1: chr(ord('A') + i) for i in range(26)},  # 0x01-0x1A = A-Z
        0x00: ' ',
        **{i + 0x1B: chr(ord('a') + i) for i in range(26)},  # 0x1B+ = a-z
        0xFF: None,
    }

    @classmethod
    def get_all_charsets(cls) -> List[Tuple[str, Dict[int, str]]]:
        """Retorna todos os charsets conhecidos."""
        return [
            ('Message Box', cls.MESSAGE_CHARSET),
            ('Title Screen', cls.TITLE_CHARSET),
            ('ASCII', cls.ASCII_CHARSET),
            ('Shift -1', cls.SHIFT_MINUS_ONE),
        ]


class PointerTableScanner:
    """Detector avançado de tabelas de ponteiros."""

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data

    def find_pointer_tables(self, min_size: int = 10, max_size: int = 200) -> List[Tuple[int, List[int]]]:
        """Encontra tabelas de ponteiros válidas."""
        tables = []
        rom_size = len(self.rom_data)

        for offset in range(0, rom_size - 20, 2):
            # Lê primeiro ponteiro
            ptr1 = self.rom_data[offset] | (self.rom_data[offset + 1] << 8)

            # Pula se não parece ponteiro SNES válido
            if not (0x8000 <= ptr1 < 0xFFFF):
                continue

            # Tenta ler sequência de ponteiros
            pointers = [ptr1]
            pos = offset + 2

            while len(pointers) < max_size and pos + 2 <= rom_size:
                next_ptr = self.rom_data[pos] | (self.rom_data[pos + 1] << 8)

                # Validações:
                # 1. Dentro do range SNES
                if not (0x8000 <= next_ptr < 0xFFFF):
                    break

                # 2. Incremento razoável (< 4KB)
                if pointers:
                    diff = next_ptr - pointers[-1]
                    if not (0 < diff < 4096):
                        break

                pointers.append(next_ptr)
                pos += 2

            # Só aceita se tem tamanho mínimo
            if len(pointers) >= min_size:
                # Evita duplicatas (tabelas sobrepostas)
                is_duplicate = any(
                    abs(offset - existing[0]) < 10
                    for existing in tables
                )

                if not is_duplicate:
                    tables.append((offset, pointers))

        return tables


class EnhancedValidator:
    """Validador super expandido com ~1000 palavras de jogos."""

    # Vocabulário massivamente expandido
    VOCABULARY = {
        # === AÇÕES (Verbos) ===
        'ATTACK', 'DEFEND', 'BLOCK', 'DODGE', 'STRIKE', 'SLASH', 'STAB', 'SHOOT',
        'THROW', 'CATCH', 'GRAB', 'HOLD', 'PUSH', 'PULL', 'LIFT', 'DROP',
        'JUMP', 'RUN', 'WALK', 'CLIMB', 'SWIM', 'DIVE', 'CRAWL', 'CROUCH',
        'OPEN', 'CLOSE', 'UNLOCK', 'LOCK', 'ENTER', 'EXIT', 'LEAVE', 'GO',
        'TAKE', 'GIVE', 'USE', 'EQUIP', 'WEAR', 'REMOVE', 'ACTIVATE', 'DEACTIVATE',
        'TALK', 'SPEAK', 'LISTEN', 'HEAR', 'LOOK', 'WATCH', 'SEE', 'SEARCH',
        'FIND', 'LOSE', 'GET', 'OBTAIN', 'RECEIVE', 'STEAL', 'BUY', 'SELL',
        'TRADE', 'EXCHANGE', 'COLLECT', 'GATHER', 'PICK', 'CHOOSE', 'SELECT',
        'READ', 'WRITE', 'DRAW', 'PAINT', 'BUILD', 'CREATE', 'DESTROY', 'BREAK',
        'HIT', 'PUNCH', 'KICK', 'STOMP', 'SMASH', 'CRUSH', 'SQUASH', 'PRESS',
        'SPIN', 'TURN', 'ROTATE', 'FLIP', 'ROLL', 'BOUNCE', 'SLIDE', 'GLIDE',
        'FLY', 'FLOAT', 'FALL', 'LAND', 'CRASH', 'EXPLODE', 'BURN', 'FREEZE',
        'HEAL', 'CURE', 'RESTORE', 'REVIVE', 'POISON', 'PARALYZE', 'SLEEP', 'CONFUSE',
        'CAST', 'SUMMON', 'CALL', 'INVOKE', 'CHARGE', 'POWER', 'TRANSFORM', 'CHANGE',

        # === STATUS/SISTEMA ===
        'START', 'BEGIN', 'END', 'FINISH', 'COMPLETE', 'CONTINUE', 'PAUSE', 'STOP',
        'SAVE', 'LOAD', 'RESET', 'RESTART', 'QUIT', 'EXIT', 'CANCEL', 'CONFIRM',
        'SELECT', 'CHOOSE', 'OPTION', 'SETTING', 'CONFIG', 'MENU', 'TITLE', 'SCREEN',
        'GAME', 'PLAY', 'PLAYER', 'CHARACTER', 'LEVEL', 'STAGE', 'ROUND', 'TURN',
        'WIN', 'LOSE', 'VICTORY', 'DEFEAT', 'DEATH', 'DEAD', 'ALIVE', 'LIFE', 'LIVES',
        'SCORE', 'POINT', 'POINTS', 'BONUS', 'EXTRA', 'COMBO', 'CHAIN', 'STREAK',
        'HEALTH', 'HP', 'MP', 'SP', 'EP', 'MAGIC', 'MANA', 'ENERGY', 'POWER', 'STAMINA',
        'TIME', 'TIMER', 'CLOCK', 'SECOND', 'MINUTE', 'HOUR', 'DAY', 'NIGHT',
        'RANK', 'RANKING', 'RECORD', 'BEST', 'HIGH', 'LOW', 'NEW', 'OLD',

        # === DIREÇÕES ===
        'UP', 'DOWN', 'LEFT', 'RIGHT', 'NORTH', 'SOUTH', 'EAST', 'WEST',
        'FORWARD', 'BACKWARD', 'BACK', 'NEXT', 'PREVIOUS', 'PREV', 'FIRST', 'LAST',
        'TOP', 'BOTTOM', 'MIDDLE', 'CENTER', 'SIDE', 'CORNER', 'EDGE', 'BETWEEN',
        'ABOVE', 'BELOW', 'OVER', 'UNDER', 'INSIDE', 'OUTSIDE', 'IN', 'OUT',
        'NEAR', 'FAR', 'CLOSE', 'DISTANT', 'HERE', 'THERE', 'WHERE', 'TOWARD',

        # === ITENS ===
        'ITEM', 'WEAPON', 'ARMOR', 'SHIELD', 'HELMET', 'BOOTS', 'GLOVE', 'GLOVES',
        'SWORD', 'BLADE', 'KNIFE', 'DAGGER', 'AXE', 'HAMMER', 'CLUB', 'STAFF',
        'SPEAR', 'LANCE', 'BOW', 'ARROW', 'GUN', 'PISTOL', 'RIFLE', 'CANNON',
        'BOMB', 'GRENADE', 'MINE', 'DYNAMITE', 'TNT', 'EXPLOSIVE', 'ROCKET', 'MISSILE',
        'POTION', 'ELIXIR', 'MEDICINE', 'HERB', 'ANTIDOTE', 'REMEDY', 'TONIC', 'ETHER',
        'FOOD', 'BREAD', 'MEAT', 'FRUIT', 'WATER', 'DRINK', 'WINE', 'BEER', 'ALE',
        'KEY', 'CARD', 'PASS', 'TICKET', 'TOKEN', 'COIN', 'GOLD', 'SILVER', 'GEM',
        'RING', 'NECKLACE', 'AMULET', 'CHARM', 'PENDANT', 'BRACELET', 'EARRING',
        'MAP', 'COMPASS', 'TORCH', 'LANTERN', 'CANDLE', 'LIGHT', 'ROPE', 'LADDER',
        'BOOK', 'SCROLL', 'LETTER', 'NOTE', 'PAPER', 'PEN', 'INK', 'DIARY',
        'BAG', 'PACK', 'POUCH', 'SACK', 'BOX', 'CHEST', 'CASE', 'CONTAINER',
        'STAR', 'MUSHROOM', 'FLOWER', 'FEATHER', 'CAPE', 'SHELL', 'BLOCK',

        # === PERSONAGENS/INIMIGOS ===
        'MARIO', 'LUIGI', 'YOSHI', 'PEACH', 'TOAD', 'BOWSER', 'KOOPA', 'GOOMBA',
        'HERO', 'WARRIOR', 'KNIGHT', 'MAGE', 'WIZARD', 'WITCH', 'SORCERER', 'PRIEST',
        'FIGHTER', 'MONK', 'THIEF', 'NINJA', 'RANGER', 'HUNTER', 'ARCHER', 'PALADIN',
        'DRAGON', 'DEMON', 'DEVIL', 'BEAST', 'MONSTER', 'CREATURE', 'ENEMY', 'FOE',
        'GOBLIN', 'ORC', 'OGRE', 'TROLL', 'GIANT', 'GOLEM', 'UNDEAD', 'ZOMBIE',
        'SKELETON', 'GHOST', 'SPIRIT', 'PHANTOM', 'WRAITH', 'VAMPIRE', 'WEREWOLF',
        'SLIME', 'BLOB', 'OOZE', 'JELLY', 'WORM', 'SNAKE', 'SPIDER', 'BAT', 'RAT',
        'WOLF', 'BEAR', 'TIGER', 'LION', 'EAGLE', 'HAWK', 'CROW', 'RAVEN',
        'KING', 'QUEEN', 'PRINCE', 'PRINCESS', 'LORD', 'LADY', 'DUKE', 'BARON',
        'KNIGHT', 'GUARD', 'SOLDIER', 'WARRIOR', 'MERCENARY', 'BANDIT', 'PIRATE',
        'MERCHANT', 'VENDOR', 'SHOPKEEPER', 'TRADER', 'DEALER', 'SELLER', 'BUYER',
        'VILLAGER', 'CITIZEN', 'PEASANT', 'FARMER', 'HUNTER', 'FISHERMAN', 'MINER',
        'ELDER', 'SAGE', 'ORACLE', 'PROPHET', 'MASTER', 'TEACHER', 'STUDENT', 'PUPIL',
        'FRIEND', 'ALLY', 'PARTNER', 'COMPANION', 'COMRADE', 'RIVAL', 'OPPONENT',

        # === LOCAIS ===
        'WORLD', 'LAND', 'REALM', 'KINGDOM', 'EMPIRE', 'NATION', 'COUNTRY', 'REGION',
        'TOWN', 'CITY', 'VILLAGE', 'HAMLET', 'SETTLEMENT', 'OUTPOST', 'CAMP', 'BASE',
        'CASTLE', 'PALACE', 'FORTRESS', 'FORT', 'STRONGHOLD', 'CITADEL', 'KEEP', 'TOWER',
        'DUNGEON', 'PRISON', 'JAIL', 'CELL', 'CAGE', 'CHAMBER', 'VAULT', 'CRYPT',
        'CAVE', 'CAVERN', 'GROTTO', 'MINE', 'PIT', 'HOLE', 'TUNNEL', 'PASSAGE',
        'FOREST', 'WOODS', 'JUNGLE', 'GROVE', 'THICKET', 'CLEARING', 'GLADE', 'MEADOW',
        'MOUNTAIN', 'HILL', 'PEAK', 'SUMMIT', 'CLIFF', 'RIDGE', 'VALLEY', 'CANYON',
        'DESERT', 'WASTELAND', 'BADLANDS', 'DUNES', 'OASIS', 'SAND', 'PLAIN', 'PLAINS',
        'LAKE', 'POND', 'POOL', 'RIVER', 'STREAM', 'CREEK', 'BROOK', 'WATERFALL',
        'OCEAN', 'SEA', 'BAY', 'COAST', 'SHORE', 'BEACH', 'REEF', 'ISLAND',
        'BRIDGE', 'ROAD', 'PATH', 'TRAIL', 'ROUTE', 'WAY', 'STREET', 'ALLEY',
        'HOUSE', 'HOME', 'HUT', 'CABIN', 'COTTAGE', 'MANSION', 'VILLA', 'ESTATE',
        'INN', 'TAVERN', 'BAR', 'PUB', 'HOTEL', 'LODGE', 'HOSTEL', 'MOTEL',
        'SHOP', 'STORE', 'MARKET', 'BAZAAR', 'MALL', 'EMPORIUM', 'BOUTIQUE', 'STALL',
        'TEMPLE', 'SHRINE', 'CHURCH', 'CATHEDRAL', 'CHAPEL', 'MONASTERY', 'ABBEY',
        'SCHOOL', 'ACADEMY', 'UNIVERSITY', 'COLLEGE', 'LIBRARY', 'MUSEUM', 'HALL',
        'ARENA', 'STADIUM', 'COLISEUM', 'AMPHITHEATER', 'THEATER', 'STAGE', 'RING',
        'GATE', 'DOOR', 'ENTRANCE', 'EXIT', 'PORTAL', 'ARCH', 'WALL', 'FENCE',
        'ROOM', 'HALL', 'CORRIDOR', 'PASSAGE', 'STAIR', 'STAIRS', 'FLOOR', 'CEILING',
        'ZONE', 'AREA', 'SECTOR', 'DISTRICT', 'QUARTER', 'SECTION', 'PART', 'PLACE',

        # === ELEMENTOS/NATUREZA ===
        'FIRE', 'WATER', 'EARTH', 'WIND', 'ICE', 'LIGHTNING', 'THUNDER', 'LIGHT',
        'DARK', 'SHADOW', 'HOLY', 'EVIL', 'POISON', 'ACID', 'METAL', 'WOOD',
        'SUN', 'MOON', 'STAR', 'SKY', 'CLOUD', 'RAIN', 'SNOW', 'STORM', 'WIND',
        'TREE', 'PLANT', 'FLOWER', 'GRASS', 'LEAF', 'ROOT', 'BRANCH', 'SEED',
        'ROCK', 'STONE', 'CRYSTAL', 'ORE', 'METAL', 'IRON', 'STEEL', 'BRONZE',

        # === CONECTIVAS E PALAVRAS COMUNS ===
        'THE', 'AND', 'OR', 'BUT', 'FOR', 'NOR', 'YET', 'SO', 'IF', 'THEN',
        'OF', 'TO', 'IN', 'ON', 'AT', 'BY', 'WITH', 'FROM', 'INTO', 'ONTO',
        'THROUGH', 'DURING', 'BEFORE', 'AFTER', 'UNTIL', 'WHILE', 'SINCE', 'THOUGH',
        'YOU', 'YOUR', 'YOURS', 'I', 'ME', 'MY', 'MINE', 'HE', 'HIM', 'HIS',
        'SHE', 'HER', 'HERS', 'IT', 'ITS', 'WE', 'US', 'OUR', 'OURS',
        'THEY', 'THEM', 'THEIR', 'THEIRS', 'THIS', 'THAT', 'THESE', 'THOSE',
        'WHO', 'WHOM', 'WHOSE', 'WHICH', 'WHAT', 'WHEN', 'WHERE', 'WHY', 'HOW',
        'CAN', 'COULD', 'MAY', 'MIGHT', 'MUST', 'SHALL', 'SHOULD', 'WILL', 'WOULD',
        'DO', 'DOES', 'DID', 'DONE', 'DOING', 'BE', 'AM', 'IS', 'ARE', 'WAS',
        'WERE', 'BEEN', 'BEING', 'HAVE', 'HAS', 'HAD', 'HAVING',
        'NOT', 'NO', 'NONE', 'NEVER', 'NOTHING', 'NOWHERE', 'NOBODY', 'NEITHER',
        'YES', 'OK', 'OKAY', 'SURE', 'FINE', 'GOOD', 'GREAT', 'NICE', 'WELL',
        'BAD', 'POOR', 'TERRIBLE', 'AWFUL', 'HORRIBLE', 'WORSE', 'WORST', 'BETTER',
        'BEST', 'MORE', 'MOST', 'LESS', 'LEAST', 'FEW', 'LITTLE', 'MUCH', 'MANY',
        'ALL', 'EVERY', 'EACH', 'SOME', 'ANY', 'BOTH', 'EITHER', 'NEITHER', 'SEVERAL',
        'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE', 'TEN',
        'FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH', 'LAST', 'NEXT', 'OTHER', 'ANOTHER',

        # === ADJETIVOS COMUNS ===
        'BIG', 'SMALL', 'LARGE', 'TINY', 'HUGE', 'GIANT', 'MINI', 'LITTLE', 'GREAT',
        'LONG', 'SHORT', 'TALL', 'HIGH', 'LOW', 'DEEP', 'SHALLOW', 'WIDE', 'NARROW',
        'THICK', 'THIN', 'FAT', 'SLIM', 'HEAVY', 'LIGHT', 'STRONG', 'WEAK', 'TOUGH',
        'HARD', 'SOFT', 'ROUGH', 'SMOOTH', 'SHARP', 'DULL', 'BRIGHT', 'DARK', 'DIM',
        'HOT', 'COLD', 'WARM', 'COOL', 'FREEZING', 'BURNING', 'WET', 'DRY', 'DAMP',
        'FAST', 'SLOW', 'QUICK', 'RAPID', 'SWIFT', 'SPEEDY', 'SLUGGISH', 'LAZY',
        'FULL', 'EMPTY', 'COMPLETE', 'INCOMPLETE', 'WHOLE', 'HALF', 'PARTIAL', 'TOTAL',
        'OPEN', 'CLOSED', 'LOCKED', 'UNLOCKED', 'BLOCKED', 'CLEAR', 'FREE', 'TRAPPED',
        'SAFE', 'DANGEROUS', 'RISKY', 'SECURE', 'PROTECTED', 'EXPOSED', 'HIDDEN', 'VISIBLE',
        'OLD', 'NEW', 'YOUNG', 'ANCIENT', 'MODERN', 'CURRENT', 'FRESH', 'STALE',
        'CLEAN', 'DIRTY', 'PURE', 'IMPURE', 'CLEAR', 'MUDDY', 'FILTHY', 'PRISTINE',
        'TRUE', 'FALSE', 'REAL', 'FAKE', 'GENUINE', 'AUTHENTIC', 'ORIGINAL', 'COPY',
        'SPECIAL', 'NORMAL', 'REGULAR', 'UNUSUAL', 'RARE', 'COMMON', 'UNIQUE', 'STRANGE',
        'DIFFERENT', 'SAME', 'SIMILAR', 'IDENTICAL', 'EQUAL', 'UNEQUAL', 'ALIKE', 'UNLIKE',
        'POSSIBLE', 'IMPOSSIBLE', 'EASY', 'HARD', 'DIFFICULT', 'SIMPLE', 'COMPLEX',
        'READY', 'PREPARED', 'SET', 'EQUIPPED', 'ARMED', 'LOADED', 'FILLED', 'CHARGED',

        # === VERBOS EXTRAS ===
        'HELP', 'SAVE', 'RESCUE', 'PROTECT', 'GUARD', 'DEFEND', 'SHIELD', 'COVER',
        'TRAP', 'CAPTURE', 'CATCH', 'SEIZE', 'GRAB', 'RELEASE', 'FREE', 'ESCAPE',
        'DEFEAT', 'BEAT', 'OVERCOME', 'CONQUER', 'VANQUISH', 'TRIUMPH', 'PREVAIL',
        'THANK', 'THANKS', 'PLEASE', 'SORRY', 'WELCOME', 'HELLO', 'HI', 'GOODBYE',
        'BYE', 'FAREWELL', 'GREETINGS', 'SALUTE', 'BOW', 'KNEEL', 'STAND', 'SIT',

        # === PALAVRAS ESPECÍFICAS DE JOGOS ===
        'TOADSTOOL', 'PRINCESS', 'TRAPPED', 'BUTTON', 'PRESSING', 'JUMPING',
        'STOMP', 'DRAGON', 'COINS', 'BLOCKS', 'SWITCH', 'PALACE', 'SUNKEN',
        'CHOCO', 'CHOCOLATE', 'VANILLA', 'DONUT', 'BUTTER', 'CHEESE', 'SODA',
        'SECRET', 'BONUS', 'CONTINUE', 'SAVED', 'EXITS', 'FURTHER', 'BETWEEN',
        'FILL', 'PLACE', 'PLACES', 'PUSH', 'PUSHED', 'BREAK', 'FENCE', 'POOL',
        'DIFFERENT', 'COMPLETE', 'EXPLORE', 'FOUND', 'LOST', 'MIDDLE', 'BALANCE',
        'ABLE', 'JUST', 'ALREADY', 'ALSO', 'STILL', 'EVEN', 'ONLY', 'VERY',
    }

    @classmethod
    def is_valid(cls, text: str) -> bool:
        """Validação super rigorosa."""
        text_clean = text.replace('-', ' ').strip()

        if len(text_clean) < 3:
            return False

        # Mínimo 40% alfabético
        alpha_ratio = sum(1 for c in text_clean if c.isalpha()) / len(text_clean)
        if alpha_ratio < 0.4:
            return False

        # Procura palavra do vocabulário
        words = text_clean.upper().split()
        for word in words:
            if word in cls.VOCABULARY:
                return True

        # Verifica substrings (>= 4 chars)
        text_upper = text_clean.upper()
        for vocab_word in cls.VOCABULARY:
            if len(vocab_word) >= 4 and vocab_word in text_upper:
                return True

        # Mínimo de vogais
        vowels = sum(1 for c in text_clean if c.upper() in 'AEIOU')
        if vowels < len(text_clean) * 0.15:
            return False

        # Não repetitivo
        if len(set(text_clean.replace(' ', ''))) < 4:
            return False

        # Se tem >12 caracteres alfabéticos, aprova condicionalmente
        if sum(1 for c in text_clean if c.isalpha()) >= 12:
            return True

        return False


class UltimateExtractor:
    """Extrator definitivo: charsets conhecidos + métodos avançados."""

    def __init__(self, rom_path: str):
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.all_texts = set()
        self.stats = defaultdict(int)

    def load_rom(self):
        """Carrega ROM."""
        print(f"📂 Carregando ROM: {self.rom_path.name}")
        with open(self.rom_path, 'rb') as f:
            self.rom_data = f.read()
        print(f"✅ {len(self.rom_data):,} bytes\n")

    def extract_all(self) -> List[str]:
        """Pipeline completo."""
        print("=" * 80)
        print("🏆 ULTIMATE EXTRACTOR - MÁXIMA COBERTURA")
        print("=" * 80)
        print()

        self.load_rom()

        # MÉTODO 1: Varredura com charsets conhecidos
        print("=" * 80)
        print("MÉTODO 1: CHARSETS CONHECIDOS (Varredura Completa)")
        print("=" * 80)

        for charset_name, charset in KnownCharsets.get_all_charsets():
            texts = self._scan_with_charset(charset)
            self.all_texts.update(texts)
            self.stats[f'charset_{charset_name}'] = len(texts)
            print(f"   {charset_name}: {len(texts)} textos extraídos")

        print()

        # MÉTODO 2: Seguir ponteiros
        print("=" * 80)
        print("MÉTODO 2: TABELAS DE PONTEIROS")
        print("=" * 80)

        scanner = PointerTableScanner(self.rom_data)
        tables = scanner.find_pointer_tables(min_size=10, max_size=100)
        print(f"   Encontradas {len(tables)} tabelas válidas")

        for charset_name, charset in KnownCharsets.get_all_charsets():
            for table_offset, pointers in tables:
                texts = self._extract_from_pointers(pointers, charset)
                self.all_texts.update(texts)
                self.stats['pointer_following'] += len(texts)

        print(f"   Total extraído via ponteiros: {self.stats['pointer_following']} textos")
        print()

        # MÉTODO 3: Validação expandida
        print("=" * 80)
        print("MÉTODO 3: VALIDAÇÃO INTELIGENTE")
        print("=" * 80)

        validated = [t for t in self.all_texts if EnhancedValidator.is_valid(t)]
        print(f"   {len(validated)} de {len(self.all_texts)} textos passaram")
        print()

        # MÉTODO 4: Remoção de fragmentos sobrepostos
        print("=" * 80)
        print("MÉTODO 4: CONSOLIDAÇÃO")
        print("=" * 80)

        final_texts = self._remove_substrings(validated)
        print(f"   {len(validated)} → {len(final_texts)} textos únicos")
        print()

        return sorted(final_texts, key=lambda x: (-len(x), x.upper()))

    def _scan_with_charset(self, charset: Dict[int, str]) -> List[str]:
        """Varre ROM com charset específico."""
        texts = []
        current_text = []

        for byte in self.rom_data:
            if byte in charset:
                char = charset[byte]
                if char is None:  # Terminador
                    if len(current_text) >= 4:
                        texts.append(''.join(current_text).strip())
                    current_text = []
                elif char == '\n':
                    if len(current_text) >= 4:
                        texts.append(''.join(current_text).strip())
                    current_text = []
                else:
                    current_text.append(char)
            else:
                if len(current_text) >= 4:
                    texts.append(''.join(current_text).strip())
                current_text = []

        return [t for t in texts if t]  # Remove vazios

    def _extract_from_pointers(self, pointers: List[int],
                              charset: Dict[int, str]) -> List[str]:
        """Extrai textos seguindo ponteiros."""
        texts = []

        for ptr in pointers:
            # Converte ponteiro SNES para offset ROM
            rom_offset = ptr - 0x8000 if ptr >= 0x8000 else ptr

            if rom_offset < 0 or rom_offset >= len(self.rom_data):
                continue

            # Extrai string
            text = []
            pos = rom_offset

            while pos < len(self.rom_data) and len(text) < 200:
                byte = self.rom_data[pos]

                if byte in charset:
                    char = charset[byte]
                    if char is None or char == '\n':
                        break
                    text.append(char)
                    pos += 1
                else:
                    break

            if len(text) >= 4:
                texts.append(''.join(text).strip())

        return texts

    def _remove_substrings(self, texts: List[str]) -> List[str]:
        """Remove textos que são substrings de outros."""
        sorted_texts = sorted(texts, key=len, reverse=True)
        result = []

        for text in sorted_texts:
            is_substring = any(
                text != other and text in other
                for other in result
            )

            if not is_substring:
                result.append(text)

        return result

    def save_results(self, output_path: str):
        """Salva resultados."""
        output_file = Path(output_path)

        with open(output_file, 'w', encoding='utf-8') as f:
            for text in sorted(self.all_texts, key=lambda x: (-len(x), x.upper())):
                f.write(f"{text}\n")

        print(f"💾 {len(self.all_texts)} textos salvos em: {output_file.name}")


def main():
    """Função principal."""

    rom_path = r"C:\Users\celso\OneDrive\Área de Trabalho\PROJETO_V5_OFICIAL\rom-translation-framework\ROMs\Super Nintedo\Super Mario World.smc"

    if not Path(rom_path).exists():
        print(f"❌ ROM não encontrada")
        return

    extractor = UltimateExtractor(rom_path)
    texts = extractor.extract_all()

    print("=" * 80)
    print("📝 PREVIEW (PRIMEIROS 150 TEXTOS):")
    print("=" * 80)
    print()

    for i, text in enumerate(texts[:150], 1):
        print(f"{i:3d}. {text}")

    if len(texts) > 150:
        print(f"\n... e mais {len(texts) - 150} textos")

    output_path = rom_path.replace('.smc', '_ULTIMATE.txt')
    extractor.save_results(output_path)

    print("\n" + "=" * 80)
    print("📊 COMPARAÇÃO FINAL:")
    print("=" * 80)
    print(f"   Método Dual Charset:  72 textos")
    print(f"   Ultimate Extractor: {len(texts)} textos")
    improvement = ((len(texts) - 72) / 72 * 100) if len(texts) > 72 else 0
    print(f"   Melhoria: +{improvement:.1f}%")
    print("=" * 80)


if __name__ == '__main__':
    main()
