# -*- coding: utf-8 -*-
"""Create a smaller test file from main.bin"""

# Read first 5KB from main.bin
with open(r'G:\Darkness Within\DarknessWithin\files\main.bin', 'rb') as f:
    data = f.read(5000)

# Save test file
with open(r'G:\Darkness Within\DarknessWithin\files\main_test.bin', 'wb') as f:
    f.write(data)

print('✅ Arquivo de teste criado!')
print(f'   Original: 2.074 KB')
print(f'   Teste: {len(data)} bytes (~0.25% do original)')
print('\nAgora execute:')
print('python examples/translate_single_file.py "G:\\Darkness Within\\DarknessWithin\\files\\main_test.bin" "AIzaSyA5XDMtNNBXmnThzdy4UV_0Hl3SwReoFeE"')
