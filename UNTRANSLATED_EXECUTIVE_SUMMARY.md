# Untranslated Safe Entries Analysis - Executive Summary

**Date**: 2026-02-20  
**ROM**: Ultima (DE9F8517)  
**Total Untranslated Safe Entries**: 289  
**File**: `ROMs/Master System/DE9F8517/2_traducao/DE9F8517_translated.jsonl`

---

## Quick Summary

Out of the translation, **289 entries remain untranslated** (same source as destination). These fall into distinct categories with varying levels of priority and actionability.

| Category | Count | Type | Action |
|----------|-------|------|--------|
| Clean SCRIPT_OPCODE entries | 102 | Game text, character names | Review & translate |
| Questionable SCRIPT_OPCODE | 53 | Flagged as garbage/symbolic | Audit for false positives |
| **Translatable POINTER entries** | **128** | Game items, directions, verbs | **Manual translation** |
| Non-translatable POINTER | 6 | Codes, artifacts | Skip |
| **Total Actionable** | **230** | Real game content | Can be translated |

---

## Detailed Breakdown by Source

### SCRIPT_OPCODE_AUTO (155 entries)

These are entries extracted from game scripts/data.

**Status Distribution:**
- **Clean (no flags): 102 entries** ✓
  - No plausibility warnings
  - Include character names, items, mechanics
  - Examples: "Equipment", "Items", "Armour", "Talk", "Magic", "Geoffrey", "Iolo"
  - **Action**: Should be translated

- **Flagged entries: 53 entries** ⚠️
  - With GARBAGE flag: 28
  - With SYMBOLIC flag: 31
  - With LOW_PLAUSIBILITY flag: 39
  - Examples: "4-L1", "}x!@", "MDj&", "SHP:"
  - **Action**: Audit to separate real text from false positives

### POINTER (134 entries)

These are entries extracted from pointer-referenced tables.

**Categorization:**
- **Clearly translatable: 128 entries** ✓
  - Proper nouns (names of characters, places): 174 (including overlaps)
    - Examples: "Mariah", "Geoffrey", "Iolo", "Minoc", "Trinsic", "Vesper"
  - Game mechanics: "Equipment", "Items", "Magic", "Talk"
  - Directions: "North", "South", "East", "West"
  - Items & equipment: "Armour", "Axe", "Sword", "Keys", "Gems"
  - Verbs: "Search", "Open", "Heal", "Rest", "Save"
  - **Action**: Manual translation needed

- **Non-translatable: 6 entries** ✗
  - Artifacts, codes, corrupted data
  - Examples: "UTZ", "Quat", "asks:"
  - **Action**: Can be skipped

---

## High Priority for Manual Translation

**230 entries ready for translation:**

### 1. Directions (5 entries)
```
North, South, East, West, (repeated)
```

### 2. Game Actions/Verbs (11 entries)
```
Talk, Use, Search, Camp, Equipment, Items, Rest, Save, Board, Open, Heal
```

### 3. Game Elements & Items (66 entries)
```
Armour, Axe, Bomb, Keys, Gems, Ginseng, Horn, Trap, Equipment, Items, Reagents
```

### 4. Character Names (Multiple instances)
```
Geoffrey, Iolo, Shamino, Dupre, Mariah, Zorin, Shawn, Sheila, and 166+ more
```

### 5. Location Names
```
Minoc, Trinsic, Vesper, Cove, Covetous, Shame
```

### 6. Status Conditions (4 entries)
```
Dead, Poisoned, Ready, Resting
```

---

## Questionable Entries (18 total)

These entries have GARBAGE or SYMBOLIC flags and are likely NOT real game text:

```
4-L1, 5BYE, SHP:, MDj&, x+o&, t<t1, }x!@, L V:, STR:, DEX:, INT:, M P:, etc.
```

**Action**: Audit extraction rules to reduce false positives

---

## Recommendations

### Immediate Actions (High Impact)

1. **Translate 86 high-priority items**
   - Directions (5)
   - Actions/verbs (11)
   - Game elements (66)
   - Status (4)
   - Est. time: 30-60 min

2. **Manual translate ~128 POINTER names**
   - Character names
   - Location names
   - Game mechanics terms
   - Est. time: 2-4 hours

3. **Review 102 clean SCRIPT_OPCODE entries**
   - Many appear translatable
   - Includes character names, items, mechanics
   - Est. time: 1-2 hours

### Medium Priority

4. **Audit 53 flagged SCRIPT_OPCODE entries**
   - Separate real text from false positives
   - May recover 30-50% additional real entries
   - Est. time: 1-2 hours

### Lower Priority

5. **Skip 6 non-translatable POINTER entries**
   - These are codes/artifacts
   - No action needed

---

## File Outputs

Generated analysis files:
- `UNTRANSLATED_ANALYSIS.txt` - Detailed list of all 289 entries
- `UNTRANSLATED_CATEGORIZED.txt` - Entries by category (directions, names, items, etc.)
- `UNTRANSLATED_ENTRIES.csv` - Spreadsheet format for manual work
- `HIGH_PRIORITY_TRANSLATIONS.txt` - Just the actionable entries
- `UNTRANSLATED_EXECUTIVE_SUMMARY.md` - This file

---

## Translation Impact

**Current state**: 289 entries untranslated (same source/destination)  
**After recommended actions**: ~230 entries can be translated  
**Remaining**: ~18 entries (garbage/artifacts)  

**Estimated completion**: 4-8 hours of manual translation work  
**Expected quality**: High (all entries are clearly defined English text)

---

## Notes

- The game is **Ultima** for Master System (Sega)
- Many entries are character names and location names (proper nouns)
- Clear English game mechanics vocabulary makes translation straightforward
- No technical translation needed - pure game text

