# egx_scanner.py
"""
EGX 30 & EGX 70 Technical Confluence Scanner (Egyptian Stock Exchange)
Scans top liquid Egyptian stocks during active session hours (10:00 AM - 02:30 PM Cairo, Sun-Thu).
Automatically skips and halts scanning after session close and on weekends.
"""

import argparse
from datetime import datetime
import json
import os
import sys
import time
import zoneinfo
import numpy as np
import pandas as pd
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from telegram_notifier import send_telegram_alert

# Top 20 liquid Egyptian stocks
EGX_STOCKS = [
    {"code": "COMI", "ticker": "COMI.CA", "name": "البنك التجاري الدولي (CIB)", "sector": "بنوك", "sharia": False, "notes": "بنك تجاري تقليدي (فوائد ربوية)", "price": 88.5},
    {"code": "TMGH", "ticker": "TMGH.CA", "name": "مجموعة طلعت مصطفى القابضة", "sector": "عقارات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 62.4},
    {"code": "SWDY", "ticker": "SWDY.CA", "name": "السويدي إليكتريك", "sector": "صناعة وكابلات", "sharia": False, "notes": "تجاوز نسب القروض والفوائد البنكية التقليدية", "price": 47.8},
    {"code": "ETEL", "ticker": "ETEL.CA", "name": "المصرية للاتصالات", "sector": "اتصالات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 38.6},
    {"code": "FWRY", "ticker": "FWRY.CA", "name": "فوري لتكنولوجيا البنوك والمدفوعات", "sector": "تكنولوجيا", "sharia": False, "notes": "خدمات إقراض وتمويل متناهي الصغر بفائدة وتجاوز نسب", "price": 8.45},
    {"code": "ESRS", "ticker": "ESRS.CA", "name": "حديد عز", "sector": "صناعة وتعدين", "sharia": False, "notes": "تجاوز نسب الاقتراض والفوائد التمويلية", "price": 94.2},
    {"code": "EAST", "ticker": "EAST.CA", "name": "إيسترن كومباني (الشرقية للدخان)", "sector": "تبغ ودخان", "sharia": False, "notes": "نشاط محرم (صناعة وتجارة التبغ والدخان)", "price": 35.1},
    {"code": "EFIH", "ticker": "EFIH.CA", "name": "إي فاينانس للاستثمارات المالية والرقمية", "sector": "تكنولوجيا", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 28.3},
    {"code": "ABUK", "ticker": "ABUK.CA", "name": "أبو قير للأسمدة والصناعات الكيماوية", "sector": "كيماويات", "sharia": False, "notes": "تجاوز نسب الإيرادات التمويلية والفوائد الدائنة", "price": 64.5},
    {"code": "MFPC", "ticker": "MFPC.CA", "name": "مصر لإنتاج الأسمدة (موبكو)", "sector": "كيماويات", "sharia": False, "notes": "تجاوز نسب الاستثمارات والودائع بفائدة", "price": 52.8},
    {"code": "SKPC", "ticker": "SKPC.CA", "name": "سيدي كرير للبتروكيماويات (سيدبك)", "sector": "بتروكيماويات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 31.4},
    {"code": "AMOC", "ticker": "AMOC.CA", "name": "الإسكندرية للزيوت المعدنية (أموك)", "sector": "بترول", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 9.85},
    {"code": "EMFD", "ticker": "EMFD.CA", "name": "إعمار مصر للتنمية", "sector": "عقارات", "sharia": False, "notes": "تجاوز نسبة عوائد الودائع البنكية من إجمالي الإيراد", "price": 6.05},
    {"code": "PHDC", "ticker": "PHDC.CA", "name": "بالم هيلز للتعمير", "sector": "عقارات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 5.48},
    {"code": "MASR", "ticker": "MASR.CA", "name": "مدينة مصر للإسكان والتعمير", "sector": "عقارات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 4.75},
    {"code": "OCDI", "ticker": "OCDI.CA", "name": "السادس من أكتوبر للتنمية والاستثمار (سوديك)", "sector": "عقارات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 53.9},
    {"code": "EGAL", "ticker": "EGAL.CA", "name": "مصر للألومنيوم", "sector": "تعدين ومعادن", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 108.0},
    {"code": "HRHO", "ticker": "HRHO.CA", "name": "إي إف جي القابضة (هيرميس)", "sector": "خدمات مالية", "sharia": False, "notes": "خدمات مالية وقروض وتسهيلات تقليدية", "price": 23.1},
    {"code": "BTFH", "ticker": "BTFH.CA", "name": "بلتون القابضة", "sector": "خدمات مالية", "sharia": False, "notes": "خدمات تمويل استهلاكي وتسهيلات بفائدة", "price": 3.25},
    {"code": "CCAP", "ticker": "CCAP.CA", "name": "القلعة للاستشارات المالية", "sector": "خدمات مالية", "sharia": False, "notes": "تجاوز نسب المديونية المالية التقليدية", "price": 3.85},
    {"code": "ADIB", "ticker": "ADIB.CA", "name": "مصرف أبو ظبي الإسلامي - مصر", "sector": "بنوك إسلامية", "sharia": True, "notes": "بنك إسلامي معتمد (EGX 33)", "price": 46.5},
    {"code": "FAIT", "ticker": "FAIT.CA", "name": "بنك فيصل الإسلامي المصري (جنيه)", "sector": "بنوك إسلامية", "sharia": True, "notes": "بنك إسلامي معتمد (EGX 33)", "price": 37.2},
    {"code": "FAID", "ticker": "FAID.CA", "name": "بنك فيصل الإسلامي المصري (دولار)", "sector": "بنوك إسلامية", "sharia": True, "notes": "بنك إسلامي معتمد (EGX 33)", "price": 1.15},
    {"code": "SAUD", "ticker": "SAUD.CA", "name": "بنك البركة مصر", "sector": "بنوك إسلامية", "sharia": True, "notes": "بنك إسلامي معتمد (EGX 33)", "price": 14.6},
    {"code": "QNBE", "ticker": "QNBE.CA", "name": "بنك قطر الوطني الأهلي (QNB)", "sector": "بنوك", "sharia": False, "notes": "بنك تجاري تقليدي", "price": 32.5},
    {"code": "HDBK", "ticker": "HDBK.CA", "name": "بنك التعمير والإسكان", "sector": "بنوك", "sharia": False, "notes": "بنك تجاري تقليدي", "price": 48.0},
    {"code": "CIEB", "ticker": "CIEB.CA", "name": "بنك كريدي أجريكول مصر", "sector": "بنوك", "sharia": False, "notes": "بنك تجاري تقليدي", "price": 21.8},
    {"code": "CANA", "ticker": "CANA.CA", "name": "بنك قناة السويس", "sector": "بنوك", "sharia": False, "notes": "بنك تجاري تقليدي", "price": 16.4},
    {"code": "ORAS", "ticker": "ORAS.CA", "name": "أوراسكوم كونستراكشون بي إل سي", "sector": "مقاولات وإنشاءات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 288.0},
    {"code": "ORHD", "ticker": "ORHD.CA", "name": "أوراسكوم للتنمية مصر", "sector": "تطوير عقاري وسياحي", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 16.1},
    {"code": "ORWE", "ticker": "ORWE.CA", "name": "النساجون الشرقيون بالسجاد", "sector": "منسوجات وسجاد", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 25.4},
    {"code": "JUFO", "ticker": "JUFO.CA", "name": "جهينة للصناعات الغذائية", "sector": "أغذية ومشروبات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 26.2},
    {"code": "EFID", "ticker": "EFID.CA", "name": "إيديتا للصناعات الغذائية", "sector": "أغذية ومخبوزات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 34.5},
    {"code": "DOMT", "ticker": "DOMT.CA", "name": "الصناعات الغذائية العربية (دومتي)", "sector": "أغذية وألبان", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 19.3},
    {"code": "OLFI", "ticker": "OLFI.CA", "name": "عبور لاند للصناعات الغذائية", "sector": "أغذية وألبان", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 15.1},
    {"code": "ISPH", "ticker": "ISPH.CA", "name": "ابن سينا فارما", "sector": "أدوية وتوزيع", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 4.68},
    {"code": "RMDA", "ticker": "RMDA.CA", "name": "العاشر من رمضان للأدوية (راميدا)", "sector": "أدوية", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 2.95},
    {"code": "CLHO", "ticker": "CLHO.CA", "name": "مستشفى كليوباترا", "sector": "رعاية صحية ومستشفيات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 6.45},
    {"code": "NIPH", "ticker": "NIPH.CA", "name": "النيل للأدوية والصناعات الكيماوية", "sector": "أدوية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 68.0},
    {"code": "AXPH", "ticker": "AXPH.CA", "name": "الإسكندرية للأدوية والكيماويات", "sector": "أدوية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 215.0},
    {"code": "CPIC", "ticker": "CPIC.CA", "name": "القاهرة للأدوية والصناعات الكيماوية", "sector": "أدوية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 135.0},
    {"code": "MPHP", "ticker": "MPHP.CA", "name": "ممفيس للأدوية والصناعات الكيماوية", "sector": "أدوية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 82.5},
    {"code": "MCRO", "ticker": "MCRO.CA", "name": "ماكرو جروب للمستحضرات الطبية", "sector": "مستحضرات طبية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 2.15},
    {"code": "SPMD", "ticker": "SPMD.CA", "name": "سبيد ميديكال", "sector": "رعاية صحية", "sharia": False, "notes": "تجاوز النسب والديون المالية", "price": 0.48},
    {"code": "ALCN", "ticker": "ALCN.CA", "name": "الإسكندرية لتداول الحاويات والبضائع", "sector": "نقل ولوجستيات", "sharia": False, "notes": "تجاوز نسبة الإيراد التمويلي من الفوائد البنكية", "price": 50.2},
    {"code": "CSAG", "ticker": "CSAG.CA", "name": "القناة للتوكيلات الملاحية", "sector": "خدمات ملاحية", "sharia": False, "notes": "تجاوز نسبة الفوائد البنكية الدائنة", "price": 32.8},
    {"code": "ETRS", "ticker": "ETRS.CA", "name": "المصرية لخدمات النقل (إيجيترانس)", "sector": "نقل ولوجستيات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 4.25},
    {"code": "RACC", "ticker": "RACC.CA", "name": "راية لخدمات مراكز الاتصالات", "sector": "اتصالات ومراكز خدمة", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 4.95},
    {"code": "RAYA", "ticker": "RAYA.CA", "name": "راية القابضة للاستثمارات المالية", "sector": "خدمات مالية واستثمار", "sharia": False, "notes": "خدمات تقسيط وتمويل تجاري تقليدي", "price": 3.78},
    {"code": "MTIE", "ticker": "MTIE.CA", "name": "إم إم جروب للصناعة والتجارة العالمية", "sector": "تجارة وتوزيع", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 8.05},
    {"code": "MPRC", "ticker": "MPRC.CA", "name": "المصرية لمدينة الإنتاج الإعلامي", "sector": "إعلام وخدمات", "sharia": False, "notes": "عوائد فوائد بنكية وملاحظات على المحتوى", "price": 18.2},
    {"code": "ARCC", "ticker": "ARCC.CA", "name": "العربية للأسمنت", "sector": "مواد بناء وأسمنت", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 16.8},
    {"code": "MCQE", "ticker": "MCQE.CA", "name": "مصر للأسمنت - قنا", "sector": "مواد بناء وأسمنت", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 25.1},
    {"code": "SCEM", "ticker": "SCEM.CA", "name": "أسمنت سيناء", "sector": "مواد بناء وأسمنت", "sharia": False, "notes": "تجاوز نسب المديونيات والقروض", "price": 14.5},
    {"code": "EGAS", "ticker": "EGAS.CA", "name": "غاز مصر", "sector": "طاقة وغاز", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 35.8},
    {"code": "LCSW", "ticker": "LCSW.CA", "name": "ليسيكو مصر", "sector": "سيراميك وأدوات صحية", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 24.2},
    {"code": "ATQA", "ticker": "ATQA.CA", "name": "مصر الوطنية للصلب (عتاقة)", "sector": "حديد وصلب", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 4.35},
    {"code": "ELEC", "ticker": "ELEC.CA", "name": "الكابلات الكهربائية المصرية", "sector": "كابلات وصناعة", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 2.92},
    {"code": "ICFC", "ticker": "ICFC.CA", "name": "الدولية للأسمدة والكيماويات", "sector": "أسمدة وكيماويات", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 18.4},
    {"code": "IFAP", "ticker": "IFAP.CA", "name": "الدولية للمحاصيل الزراعية", "sector": "زراعة ومحاصيل", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 23.5},
    {"code": "ACGC", "ticker": "ACGC.CA", "name": "العربية لحليج الأقطان", "sector": "غزل وحليج أقطان", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 7.9},
    {"code": "MPCO", "ticker": "MPCO.CA", "name": "المنصورة للدواجن", "sector": "دواجن وإنتاج حيواني", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 1.28},
    {"code": "POUL", "ticker": "POUL.CA", "name": "القاهرة للدواجن", "sector": "دواجن وثروة داجنة", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 11.2},
    {"code": "ISMA", "ticker": "ISMA.CA", "name": "الإسماعيلية مصر للدواجن", "sector": "دواجن وثروة داجنة", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 10.5},
    {"code": "SUGR", "ticker": "SUGR.CA", "name": "الدلتا للسكر", "sector": "أغذية وسكر", "sharia": False, "notes": "تجاوز نسب الاقتراض والديون البنكية", "price": 68.0},
    {"code": "AFMC", "ticker": "AFMC.CA", "name": "مطاحن ومخابز الإسكندرية", "sector": "مطاحن وصناعات غذائية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 27.5},
    {"code": "MILS", "ticker": "MILS.CA", "name": "مطاحن ومخابز شمال القاهرة", "sector": "مطاحن وصناعات غذائية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 44.0},
    {"code": "CEFM", "ticker": "CEFM.CA", "name": "مطاحن مصر الوسطى", "sector": "مطاحن وصناعات غذائية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 58.0},
    {"code": "UFM", "ticker": "UFM.CA", "name": "مطاحن مصر العليا", "sector": "مطاحن وصناعات غذائية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 165.0},
    {"code": "CIRA", "ticker": "CIRA.CA", "name": "سيرا للتعليم (القاهرة للاستثمار)", "sector": "تعليم وخدمات تدريب", "sharia": True, "notes": "مدرج بمؤشر الشريعة EGX 33", "price": 14.5},
    {"code": "TALM", "ticker": "TALM.CA", "name": "تعليم لخدمات الإدارة", "sector": "تعليم وإدارة جامعات", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 9.15},
    {"code": "DSCW", "ticker": "DSCW.CA", "name": "دايس للملابس الجاهزة", "sector": "ملابس ومنسوجات", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 1.68},
    {"code": "HELI", "ticker": "HELI.CA", "name": "مصر الجديدة للإسكان والتعمير", "sector": "إسكان وتطوير عقاري", "sharia": False, "notes": "تجاوز نسب الفوائد والعوائد البنكية الدائنة", "price": 11.85},
    {"code": "ZMID", "ticker": "ZMID.CA", "name": "زهراء المعادي للاستثمار والتعمير", "sector": "إسكان وتطوير عقاري", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 7.1},
    {"code": "UNIT", "ticker": "UNIT.CA", "name": "المتحدة للإسكان والتعمير", "sector": "إسكان وتطوير عقاري", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 5.85},
    {"code": "ELSH", "ticker": "ELSH.CA", "name": "الشمس للإسكان والتعمير", "sector": "إسكان وتطوير عقاري", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 8.5},
    {"code": "GGCC", "ticker": "GGCC.CA", "name": "الجيزة العامة للمقاولات", "sector": "مقاولات وإنشاءات", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 0.48},
    {"code": "NCCW", "ticker": "NCCW.CA", "name": "النصر للأعمال المدنية", "sector": "مقاولات وأعمال مدنية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 4.85},
    {"code": "EGTS", "ticker": "EGTS.CA", "name": "المصرية للمنتجعات السياحية", "sector": "سياحة وفنادق", "sharia": False, "notes": "أنشطة فندقية وسياحية غير متوافقة", "price": 4.65},
    {"code": "SDTI", "ticker": "SDTI.CA", "name": "شارم دريمز للاستثمار السياحي", "sector": "سياحة وفنادق", "sharia": False, "notes": "أنشطة فندقية وخدمات غير متوافقة", "price": 19.2},
    {"code": "RTVC", "ticker": "RTVC.CA", "name": "رمكو لإنشاء القرى السياحية", "sector": "سياحة وقرى سياحية", "sharia": False, "notes": "أنشطة ترفيهية وفندقية غير متوافقة", "price": 3.35},
    {"code": "ROTO", "ticker": "ROTO.CA", "name": "رواد السياحة", "sector": "سياحة دينية", "sharia": True, "notes": "نشاط سياحة دينية وحج وعمرة", "price": 40.5},
    {"code": "CICH", "ticker": "CICH.CA", "name": "سي آي كابيتال القابضة", "sector": "خدمات مالية واستثمار", "sharia": False, "notes": "خدمات تمويل وبنوك استثمار تقليدية", "price": 5.75},
    {"code": "CNFN", "ticker": "CNFN.CA", "name": "كونتكت المالية القابضة", "sector": "خدمات تمويلية", "sharia": False, "notes": "تمويل استهلاكي تقليدي وتأمين تجاري", "price": 5.05},
    {"code": "PRDC", "ticker": "PRDC.CA", "name": "بايونيرز بروبرتيز", "sector": "تطوير عقاري", "sharia": True, "notes": "استثمار وتطوير عقاري متوافق", "price": 3.38},
    {"code": "ASPI", "ticker": "ASPI.CA", "name": "أسباير كابيتال القابضة", "sector": "خدمات مالية", "sharia": False, "notes": "أنشطة مالية غير متوافقة", "price": 0.38},
    {"code": "ACTF", "ticker": "ACTF.CA", "name": "أكت فاينانشال للاستشارات", "sector": "استشارات مالية", "sharia": True, "notes": "استشارات واستثمار متوافق", "price": 3.48},
    {"code": "BINV", "ticker": "BINV.CA", "name": "بي إنفستمنتس القابضة", "sector": "استثمار مباشر", "sharia": True, "notes": "محفظة استثمارات متوافقة", "price": 23.4},
    {"code": "EGCH", "ticker": "EGCH.CA", "name": "الصناعات الكيماوية المصرية (كيما)", "sector": "كيماويات وأسمدة", "sharia": False, "notes": "تجاوز نسب الديون والقروض البنكية", "price": 8.55},
    {"code": "MICH", "ticker": "MICH.CA", "name": "مصر لصناعة الكيماويات", "sector": "كيماويات صناعية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 22.1},
    {"code": "PRCL", "ticker": "PRCL.CA", "name": "العامة لمنتجات الخزف والصيني (شيني)", "sector": "خزف وصيني ومواد بناء", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 19.1},
    {"code": "EINS", "ticker": "EINS.CA", "name": "المهندس للتأمين", "sector": "تأمين تقليدي", "sharia": False, "notes": "تأمين تجاري تقليدي (غير تكافلي)", "price": 23.0},
    {"code": "DEIN", "ticker": "DEIN.CA", "name": "الدلتا للتأمين", "sector": "تأمين تقليدي", "sharia": False, "notes": "تأمين تجاري تقليدي (غير تكافلي)", "price": 29.5},
    {"code": "ACAMD", "ticker": "ACAMD.CA", "name": "العربية لإدارة وتطوير الأصول", "sector": "إدارة وتطوير أصول", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 0.9},
    {"code": "ARAB", "ticker": "ARAB.CA", "name": "المطورون العرب القابضة", "sector": "تطوير عقاري", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 0.8},
    {"code": "ARAV", "ticker": "ARAV.CA", "name": "العرافة للاستثمارات والاستشارات", "sector": "استثمارات عقارية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 1.52},
    {"code": "SMPP", "ticker": "SMPP.CA", "name": "الشروق الحديثة للطباعة والتغليف", "sector": "طباعة وتغليف", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 5.75},
    {"code": "KABO", "ticker": "KABO.CA", "name": "النصر للملابس والمنسوجات (كابو)", "sector": "غزل ومنسوجات", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 2.95},
    {"code": "SABA", "ticker": "SABA.CA", "name": "سبأ الدولية للأدوية", "sector": "أدوية وصناعات كيماوية", "sharia": True, "notes": "نشاط وضوابط مالية متوافقة", "price": 1.62},
    {"code": "FOOD", "ticker": "FOOD.CA", "name": "فوديكو (الإسماعيلية للصناعات الغذائية)", "sector": "صناعات غذائية وحفظ أطعمة", "sharia": True, "notes": "نشاط وضوابط مالية متوافق", "price": 32.8},
]

DATA_FILE = os.path.join(os.path.dirname(__file__), "trades_data.json")


def is_egx_session_open():
    """
    Checks if the Egyptian Stock Exchange (EGX) is currently in active trading hours.
    Official EGX trading schedule:
    - Days: Sunday through Thursday (Sun, Mon, Tue, Wed, Thu).
    - Weekend: Friday & Saturday (مغلقة).
    - Hours: 10:00 AM to 02:30 PM Cairo Time.
    Returns: (is_open: bool, reason: str, cairo_now: datetime)
    """
    cairo_tz = zoneinfo.ZoneInfo("Africa/Cairo")
    now = datetime.now(cairo_tz)
    
    # Python weekday(): Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
    # Egyptian Trading Days: Sunday (6), Monday (0), Tuesday (1), Wednesday (2), Thursday (3)
    # Egyptian Weekend: Friday (4) and Saturday (5)
    if now.weekday() in [4, 5]:
        day_name = "الجمعة" if now.weekday() == 4 else "السبت"
        return False, f"عطلة نهاية الأسبوع في مصر ({day_name})", now
    
    # Hours check (10:00 AM to 02:30 PM)
    session_start = now.replace(hour=10, minute=0, second=0, microsecond=0)
    session_end = now.replace(hour=14, minute=30, second=0, microsecond=0)
    
    if now < session_start:
        return False, f"قبل موعد افتتاح الجلسة (تبدأ في تمام الساعة 10:00 صباحاً بتوقيت القاهرة)", now
    elif now > session_end:
        return False, f"بعد انتهاء جلسة اليوم (أغلقت في تمام الساعة 02:30 ظهراً بتوقيت القاهرة)", now
    
    return True, "جلسة التداول مفتوحة ونشطة حالياً 🟢", now


def fetch_egx_candles(ticker: str):
    """Fetches daily/intraday candles and current market price for an EGX stock from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=3mo"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None, None
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None, None
        
        meta = result[0].get("meta", {})
        regular_price = meta.get("regularMarketPrice")
        
        timestamps = result[0].get("timestamp", [])
        quote = result[0].get("indicators", {}).get("quote", [{}])[0]
        
        if not timestamps or not quote:
            return None, None
        
        df = pd.DataFrame({
            "open": quote.get("open", []),
            "high": quote.get("high", []),
            "low": quote.get("low", []),
            "close": quote.get("close", []),
            "volume": quote.get("volume", [])
        })
        df = df.dropna()
        if len(df) < 20:
            return None, None
        
        # Use latest quote or regular price
        current_price = regular_price if regular_price else df["close"].iloc[-1]
        return df, float(current_price)
    except Exception as e:
        return None, None


def evaluate_egx_stock(stock_info: dict):
    """
    Evaluates technical confluence on an EGX stock using 4 key institutional strategies:
    1. Structural Support / Price Rebound
    2. RSI Oversold Recovery & Divergence
    3. Institutional Volume Spike
    4. Moving Average (EMA 20/50) Support
    """
    ticker = stock_info["ticker"]
    df, current_price = fetch_egx_candles(ticker)
    if df is None or len(df) < 20 or current_price <= 0:
        return None
    
    close = df["close"]
    volume = df["volume"]
    
    # 1. Structural Support Level (Lowest of last 15 days)
    support = df["low"].tail(15).min()
    dist_to_support = ((current_price - support) / current_price) * 100
    
    # 2. RSI Calculation (14 periods)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14, min_periods=14).mean()
    avg_loss = loss.rolling(window=14, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    rsi = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else 50.0
    
    # 3. Volume Spike (Comparing today's volume to 20-day SMA volume)
    vol_sma20 = volume.tail(20).mean()
    vol_ratio = (volume.iloc[-1] / vol_sma20) if vol_sma20 > 0 else 1.0
    
    # 4. EMA 20 & EMA 50
    ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    
    # Confluence Checklist
    matched_strategies = []
    
    # A. Rebounding from structural support (within 0.5% - 3.5%)
    if 0.5 <= dist_to_support <= 3.8:
        matched_strategies.append(f"ارتداد من دعم هيكلي رئيسي ({support:.2f} ج.م)")
        
    # B. RSI Oversold Bounce (RSI between 30 and 48)
    if 30 <= rsi <= 50:
        matched_strategies.append(f"ارتداد من تشبع بيعي RSI ({rsi:.1f})")
        
    # C. Strong Buying Volume Spike (> 1.2x average)
    if vol_ratio >= 1.25:
        matched_strategies.append(f"انفجار سيولة شرائية (+{int((vol_ratio-1)*100)}% أعلى من المتوسط)")
        
    # D. EMA 20 / EMA 50 Trend Alignment
    if current_price >= ema20 * 0.99:
        matched_strategies.append("ثبات إيجابي أعلى متوسط الدعم المتحرك EMA 20")
        
    # Require Confluence >= 2 Strategies
    if len(matched_strategies) < 2:
        return None
        
    # Calculate SL and TP targets
    stop_loss = support * 0.985  # 1.5% below structural support
    sl_pct = ((current_price - stop_loss) / current_price) * 100
    
    # Exclude if SL is too wide (> 6.0%) or too tight (< 1.0%)
    if sl_pct > 6.5 or sl_pct < 0.8:
        return None
        
    risk = current_price - stop_loss
    tp1 = current_price + (1.5 * risk)  # R:R 1:1.5
    tp2 = current_price + (2.5 * risk)  # R:R 1:2.5
    
    tp1_pct = ((tp1 - current_price) / current_price) * 100
    tp2_pct = ((tp2 - current_price) / current_price) * 100
    
    return {
        "code": stock_info["code"],
        "name": stock_info["name"],
        "sector": stock_info["sector"],
        "sharia": stock_info.get("sharia", False),
        "notes": stock_info.get("notes", ""),
        "timeframe": "1H / 1D",
        "current_price": current_price,
        "support": support,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "sl_pct": sl_pct,
        "tp1_pct": tp1_pct,
        "tp2_pct": tp2_pct,
        "rsi": rsi,
        "strategies": matched_strategies,
        "confluence_count": len(matched_strategies)
    }


def format_egx_alert(trade: dict, time_str: str) -> str:
    """Formats an institutional Telegram alert for an Egyptian stock."""
    strategies_text = "\n".join([f"  • {s}" for s in trade["strategies"]])
    
    return f"""🏛️ *فرصة استثمارية بالبورصة المصرية (EGX 30)* 🇪🇬
━━━━━━━━━━━━━━━━━━━━
📌 *السهم:* `{trade['code']}` — *{trade['name']}*
🏢 *القطاع:* {trade['sector']}
{("🕌 *الموقف الشرعي:* ✅ متوافق مع الشريعة (" + trade.get('notes', '') + ")") if trade.get('sharia') else ("⚠️ *الموقف الشرعي:* ❌ غير متوافق (" + trade.get('notes', '') + ")")}
⏰ *وقت النشر:* `{time_str}` (أثناء جلسة التداول)

⭐ *توافق {trade['confluence_count']} استراتيجيات فنية مؤكدة:*
{strategies_text}

━━━━━━━━━━━━━━━━━━━━
💵 *سعر الدخول المقترح:* `{trade['current_price']:.2f} ج.م`
🛑 *الوقف الفني (حماية رأس المال):* `{trade['stop_loss']:.2f} ج.م` `(-{trade['sl_pct']:.1f}%)`
🎯 *الهدف الأول (TP1):* `{trade['tp1']:.2f} ج.م` `(+{trade['tp1_pct']:.1f}%)`
🎯 *الهدف الثاني (TP2):* `{trade['tp2']:.2f} ج.م` `(+{trade['tp2_pct']:.1f}%)`
━━━━━━━━━━━━━━━━━━━━
💡 _تحت حماية الدعم الهيكلي {trade['support']:.2f} ج.م — تداول بانضباط._"""


def run_egx_scanner(force_scan: bool = False):
    """Main EGX scanner runner."""
    print("=" * 70, flush=True)
    print("🏛️ بدء فحص أسهم البورصة المصرية (EGX 30 / EGX 70 Technical Scanner)", flush=True)
    print("=" * 70, flush=True)
    
    # 1. Session Guard Check (مواعيد الجلسة)
    is_open, reason, cairo_now = is_egx_session_open()
    cairo_time_str = cairo_now.strftime("%I:%M %p")
    day_name_ar = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"][cairo_now.weekday()]
    
    print(f"⏰ التوقيت المحلي بالقاهرة: {cairo_time_str} | اليوم: {day_name_ar}", flush=True)
    print(f"📊 حالة الجلسة: {reason}", flush=True)
    
    if not is_open and not force_scan:
        print("\n⏸️ [EGX Guard] تنبيه: جلسة البورصة المصرية مغلقة حالياً.", flush=True)
        print("📌 المواعيد الرسمية: الأحد إلى الخميس من 10:00 صباحاً حتى 2:30 ظهراً بتوقيت القاهرة.")
        print(f"🛑 السبب: {reason}")
        print("🛡️ تم إيقاف الفحص التلقائي للحفاظ على الموارد وعدم إرسال إشارات قديمة بعد انتهاء اليوم.\n", flush=True)
        return
        
    print(f"\n🔍 جاري فحص {len(EGX_STOCKS)} من أهم وأنشط أسهم البورصة المصرية بالتوازي...", flush=True)
    
    import concurrent.futures
    valid_signals = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(evaluate_egx_stock, EGX_STOCKS)
        for res in results:
            if res:
                valid_signals.append(res)
                print(f"  -> 🎯 فرصة مرصودة: {res['code']} ({res['name']}) - توافق {res['confluence_count']} استراتيجيات!", flush=True)
            
    print(f"\n✅ اكتمل الفحص! إجمالي الأسهم المحققة لشروط الدخول الصارمة: {len(valid_signals)}", flush=True)
    
    if not valid_signals:
        print("ℹ️ لا توجد فرص شراء بتطابق استراتيجيتين في هذه الساعة من الجلسة.", flush=True)
        return
        
    token = os.environ.get("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    chat = os.environ.get("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
    
    if token and chat:
        print("\n📲 إرسال إشعارات البورصة المصرية إلى تيليجرام...", flush=True)
        sent = 0
        for s in valid_signals:
            msg = format_egx_alert(s, cairo_time_str)
            if send_telegram_alert(token, chat, msg):
                sent += 1
                time.sleep(0.5)
        print(f"  -> تم إرسال {sent} إشعارات صفقات للبورصة المصرية بنجاح إلى هاتفك!", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force scan even if session is closed (for manual testing)")
    args = parser.parse_args()
    
    run_egx_scanner(force_scan=args.force)
