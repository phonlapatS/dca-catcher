from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ConnectedAsset(BaseModel):
    symbol: str = Field(description="Ticker ของหุ้นที่เชื่อมโยงหรือได้รับผลกระทบทางอ้อม เช่น $VRT, $TSM, $BNTX")
    relationship: str = Field(description="ความสัมพันธ์: SUPPLIER, CUSTOMER, COMPETITOR, SYMPATHY_PEER")
    impact_direction: str = Field(description="POSITIVE (ได้ประโยชน์) หรือ NEGATIVE (เสียประโยชน์)")
    rationale_thai: str = Field(description="คำอธิบายสั้นๆ ว่าเชื่อมโยงและได้รับผลกระทบอย่างไร")


class CatalystArticle(BaseModel):
    headline: str
    headline_hash: str
    symbol: str
    publisher: str
    published_at: datetime
    raw_snippet: str
    premarket_price: Optional[float] = None
    premarket_volume_ratio: Optional[float] = None
    bid_ask_spread_pct: Optional[float] = None


class CatalystVerdict(BaseModel):
    is_material: bool = Field(description="ข่าวนี้กระทบต่อมูลค่าพื้นฐานหรือรายได้กิจการจริงหรือไม่ (ถ้าเป็นข่าวทั่วไป/ขยะ ให้ False)")
    materiality_score: float = Field(description="คะแนนความสำคัญ (Priority) 1.0 ถึง 10.0")
    confidence_score: float = Field(description="ระดับความน่าเชื่อถือของข่าวนี้ 0-100 (เช่น ข่าวลือ=30, ประกาศทางการ=100)")
    scope: str = Field(description="หมวดหมู่: MACRO, SECTOR, หรือ MICRO")
    sentiment: str = Field(default="NEUTRAL", description="ทิศทางของข่าวต่อราคาหุ้น: POSITIVE, NEGATIVE, หรือ NEUTRAL")
    event_category: str = Field(description="เช่น CLINICAL_TRIAL, EARNINGS, M_AND_A, REGULATORY, CONTRACT, RISK_EVENT, MACRO_EVENT")
    impact_summary: str = Field(description="ประเมินผลกระทบสั้นๆ 1-2 บรรทัด เช่น 'ส่งผลบวกลดต้นทุนระยะยาว แต่ราคาอาจพักตัวสั้นๆ'")
    bull_catalysts: str = Field(description="ปัจจัยบวกและโอกาสเติบโตทางธุรกิจ")
    bear_risks: str = Field(description="ปัจจัยลบ ความเสี่ยงที่ซ่อนอยู่ และความเสี่ยงราคาเปิดกระโดด")
    dca_guidance: str = Field(description="มุมมองกลยุทธ์ DCA แนวรับที่ปลอดภัย ไม่สนับสนุนการไล่ราคา")
    thai_summary: str = Field(description="สรุปเนื้อหาข่าวภาษาไทย 1-2 ประโยค")
    connected_stocks: List[ConnectedAsset] = Field(
        default_factory=list,
        description="รายชื่อหุ้นที่เชื่อมโยงในห่วงโซ่อุปทาน (Supply Chain / Economic Links) หรือ Sympathy Plays ที่ได้รับผลกระทบทางอ้อม"
    )
