import requests
key = 'AIzaSyB567y0_g-9jzfE-Z8dfv2acBh5eQ3c5JM'
r = requests.get(f'https://generativelanguage.googleapis.com/v1beta/models?key={key}')
models = r.json().get('models', [])
img = [m['name'] for m in models if 'image' in m['name'].lower() or 'imagen' in m['name'].lower()]
print('Image models:', img if img else 'NONE - no image generation access')
