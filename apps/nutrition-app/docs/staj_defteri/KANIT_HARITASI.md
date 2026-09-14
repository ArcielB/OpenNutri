# Günlük metinlerin teknik dayanakları

Bu dosya düzenleme ve teknik savunma içindir; basılı deftere eklenmesi gerekmez.
Kaynaklar uygulamanın bu özelliklere sahip olduğunu gösterir. Öğrencinin ilgili
işi hangi gün, kaç saatte veya tek başına yaptığını göstermez.

Temel kapsam: `apps/nutrition-app/`. Aşağıdaki `lib/`, `test/` ve `android/` yolları
bu dizine göredir. Besin veri seti üretimi, araştırma hizmetleri ve etiketleme
uygulaması günlük çalışmalara eklenmemiştir. Destek servisleri mevcut bağımlılık
olarak anlatılmıştır; bunları öğrencinin yazdığı varsayılmamıştır.

| Gün | Teknik dayanak | Özellikle korunan sınır |
| --- | --- | --- |
| 01 | `README.md`, `lib/screens/today_screen.dart` | Kapsam yalnızca mobil uygulama; kurum toplantısı/oryantasyon uydurulmadı. |
| 02 | `pubspec.yaml`, `android/app/build.gradle.kts` | Android öncelikli geliştirme; diğer platformlarda çalıştığı iddia edilmedi. |
| 03 | `lib/main.dart`, `lib/state/app_controller.dart`, `lib/services/local_store.dart` | Dış servis hazırlığı yerel günlük açılışından ayrıdır. |
| 04 | `lib/screens/home_shell.dart`, `lib/theme/app_theme.dart`, `lib/widgets/day_header.dart` | Beş ana sekme; diyet ekranı ayrı bir bağlantıdır. |
| 05 | `lib/models/food.dart`, `lib/models/diary.dart`, `lib/models/voice_resolution.dart` | Kaynak kimliği, miktar ve kayıt anındaki besin değerleri ayrı tutulur. |
| 06 | `lib/services/core_api_client.dart` | API entegrasyonu; Core veri tabanını geliştirme iddiası yok. |
| 07 | `lib/screens/food_search_screen.dart`, `test/app_regression_test.dart` | Geciken/temizlenen arama yanıtları güncellik kontrolüyle ele alınır. |
| 08 | `lib/widgets/entry_detail_sheet.dart`, `lib/widgets/serving_sheet.dart` | Besin değiştirme, miktar değiştirmeden farklıdır. |
| 09 | `lib/models/diary.dart`, `lib/models/food.dart`, `test/diary_test.dart` | Satın alınan ağırlık yalnızca tam besin bağlantılı kullanılabilir katsayıyla çevrilir. |
| 10 | `lib/services/local_store.dart`, `test/diary_test.dart` | SharedPreferences JSON; bulut eşitleme/geri yükleme yok. |
| 11 | `lib/state/app_controller.dart`, `test/controller_batch_test.dart` | İyimser görünüm, sıralı yazma ve aynı işlemi tekrar saymama. |
| 12 | `lib/widgets/entry_detail_sheet.dart`, `lib/screens/voice_log_screen.dart`, `test/entry_detail_test.dart` | İptal eski kaydı silmez; ekran kapanışı yaşam döngüsüyle uyumludur. |
| 13 | `lib/models/diary.dart`, `test/diary_test.dart`, `test/app_regression_test.dart` | Enerji, besin başına seçildikten sonra toplanır. |
| 14 | `lib/screens/nutrients_screen.dart`, `lib/services/coach_service.dart` | Eksik mikronutrient bağlamı sıfır tüketim/eksiklik tanısı değildir. |
| 15 | `lib/screens/settings_screen.dart`, `lib/state/app_controller.dart`, `test/app_regression_test.dart` | Form senkronizasyonu ilgisiz kullanıcı girdisini ezmemelidir. |
| 16 | `lib/services/voice_recorder.dart`, `lib/screens/voice_log_screen.dart` | Geçici mono 16 kHz WAV; kayıt tamamlanmadan sürekli ses yüklemesi yok. |
| 17 | `lib/services/voice_recorder.dart`, `test/voice_log_test.dart` | 1,6 s son sessizlik; 30 s sınır; süreç ölümünde temizlik garantisi yok. |
| 18 | `lib/services/voice_api_client.dart`, `lib/services/supabase_config.dart` | Anonim oturum, multipart istek, dil/zaman bağlamı; mobilde gizli Gemini anahtarı yok. |
| 19 | `lib/models/voice_resolution.dart`, `lib/screens/voice_log_screen.dart` | Model yanıtı besin ögesi ölçümü değildir; Core ayrıntısı yüklenir. |
| 20 | `lib/screens/voice_log_screen.dart`, `test/voice_log_test.dart` | Bütün öğeler kullanılabilir olmalı; varsayılan 100 g ölçülmüş miktar değildir. |
| 21 | `lib/services/voice_api_client.dart`, `lib/models/personalization.dart` | Kuyruk beklemesi dahil uçtan uca sabit süre garantisi verilmez. |
| 22 | `android/app/src/main/kotlin/org/opennutri/opennutri_app/VoiceLogWidgetProvider.kt`, `android/app/src/main/kotlin/org/opennutri/opennutri_app/MainActivity.kt`, `lib/services/android_widget_bridge.dart` | Soğuk/sıcak başlangıç ve bir kez tüketilen Intent. |
| 23 | `lib/screens/settings_screen.dart`, `lib/screens/voice_log_screen.dart`, `test/widget_setup_test.dart` | Yerleşimi kişi onaylar; kaydetme bitmeden arka planda devam vaadi yok. |
| 24 | `lib/models/personalization.dart`, `lib/screens/diets_screen.dart`, `test/personalization_test.dart` | Altı şablon; mevcut kalori hedefi kullanılır; haftalık menü yok. |
| 25 | `lib/services/coach_service.dart`, `lib/screens/home_shell.dart`, `lib/widgets/daily_coach_card.dart` | Öneri tarihli anlık özettir; her günlük değişikliği model çağrısı değildir. |
| 26 | `lib/screens/coach_screen.dart`, `lib/models/personalization.dart` | Görüşme oturumluk; yalnız açık ifadelerden kalıcı tercih adayları; anlam kuralı model talimatına dayanır. |
| 27 | `lib/screens/oracle_screen.dart`, `test/app_regression_test.dart` | Oracle açılınca yüklenir ve Core aramasına yönlendirir; matematiksel optimum iddiası yok. |
| 28 | `lib/screens/settings_screen.dart`, `lib/screens/voice_log_screen.dart`, `test/widget_setup_test.dart` | Ayrı izinler, kapatma seçeneği ve görünmeyen bileşenin Future hatası. |
| 29 | `test/`, `analysis_options.yaml` | 14 Eylül'de 44 Flutter testi + temiz analiz; tam cihaz/konuşma ölçümü değil. |
| 30 | `pubspec.yaml`, `README.md`, `../../../../docs/consumer_app_audit_2026-09-05.md` | APK 1.1.2+5 kanıtı 5 Eylül denetiminden; mağaza yayını veya yeni kurulum iddiası yok. |

## Kaynak ve doğrulama ayrımı

- Teknik davranış haritası: [consumer_app.md](../../../../docs/consumer_app.md).
- Tarihli ölçüm/kurulum kanıtı: [5 Eylül denetimi](../../../../docs/consumer_app_audit_2026-09-05.md).
- Bu belge hazırlanırken 14 Eylül 2026 tarihinde `flutter analyze --no-pub` ve
  `flutter test --no-pub --reporter expanded` yeniden çalıştırıldı: temiz analiz,
  44 test başarılı. Yeni telefon etkileşimi veya canlı yapay zekâ çağrısı yapılmadı.
- İncelenen uygulama sürümü: `1.1.2+5`. Belge hazırlanırken uygulama kodu değişmedi.
- İlgili geçmiş: `9406337` (ilk Flutter günlük), `60aaa88` (günlük arayüzü),
  `e82d7ae` (hızlı kayıt/araç takımı), `2f93b18` (kişiselleştirme), `3dab691`
  (denetim düzeltmeleri), `79680cf` (miktar penceresi), `9cc6bf6` (araç takımı
  kurulumu ve model gösterimi). Bu kimlikler gelişim kanıtıdır, devam çizelgesi değildir.
- Önceki değerlendirmede verilen “yaklaşık 40 günlük iş kapsamı” tahmini deftere
  gerçek süre veya kişisel çalışma kanıtı olarak aktarılmadı.

## Doldurulacak veya doğrulanacak bilgiler

Üniversite/bölüm, öğrenci adı/numarası, kurum/adres, sorumlu kişi/unvanı, gerçek
günlük tarihler ve hangi işlerin öğrenciye ait olduğu henüz kullanıcı tarafından
doğrulanmadı. Örneklerdeki kişisel bilgiler, imzalar, kurum isimleri ve tarihler
yeni belgeye aktarılmadı. Resmî kapak ve kurum onayı için ilgili kurumun formu
kullanılmalıdır. Bu çalışma kurumsal staj kabul kararı vermez.
