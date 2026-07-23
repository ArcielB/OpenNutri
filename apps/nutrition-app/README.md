# OpenNutri Nutrition App

Flutter client for the OpenNutri Core API. The first release supports a local
daily diary, live combined USDA food search, USDA portion or gram entry, deterministic
nutrient scaling, daily macro totals, a complete nutrient report, and editable
targets.

When the selected food has a validated source-linked refuse factor, gram entry can
switch between edible and as-purchased weight. Diary entries retain the entered
weight, basis, and converted edible weight; nutrients are always scaled from edible
grams.

## Run

```bash
flutter pub get
flutter run
```

The default API is the deployed OpenNutri Core service. Override it at build
time when testing another environment:

```bash
flutter run \
  --dart-define=OPENNUTRI_API_BASE_URL=http://127.0.0.1:8000
```

For web development, use port `5173`, which is currently allowed by the API's
CORS configuration:

```bash
flutter run -d chrome --web-port=5173
```

## Validate

```bash
flutter analyze
flutter test
flutter build apk --debug
flutter build web
```
