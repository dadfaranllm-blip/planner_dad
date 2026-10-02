# Planner Mobile

نسخه موبایل با API مرکزی `https://planner.datholding.ir/api` کار می‌کند.

امکانات این نسخه:
- ورود ایمیل/رمز + Google + Apple با deep-link `planner://oauth`
- کارها و رویدادهای باز با همگام‌سازی state بعد از «انجام شد/ادامه دارد»
- ثبت کار و رویداد با تاریخ/زمان شمسی
- «ادامه دارد» با انتخاب تاریخ شمسی جدید
- تقویم شمسی واقعی
- پیام‌رسان 1:1
- pagination لیست‌ها
- Android AppWidget واقعی با تعداد کارها/رویدادهای باز

برای ساخت Android محلی:

```bash
cd mobile
./build_android.sh
```

اسکریپت ابتدا یک Android host تمیز با Flutter فعلی می‌سازد، سپس deep-link و Widget را به آن اضافه می‌کند تا فایل‌های قدیمی Gradle/launcher وارد build نشوند.
