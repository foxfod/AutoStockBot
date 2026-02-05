REST
해외속보(제목) [해외주식-055]

호출테스트

개별문서 다운로드
해외속보(제목) [해외주식-055]정보 Method, URL, 실전 Domain, 모의 Domain, Format, Content-Type
Method	GET	URL	/uapi/overseas-price/v1/quotations/brknews-title
실전 Domain	https://openapi.koreainvestment.com:9443	모의 Domain	미지원
실전 TR ID	FHKST01011801	모의 TR ID	모의투자 미지원
Format		Content-Type	
개요
해외속보(제목) API입니다.
한국투자 HTS(eFriend Plus) > [7704] 해외속보 화면 의 기능을 API로 개발한 사항으로, 해당 화면을 참고하시면 기능을 이해하기 쉽습니다.

최대 100건까지 조회 가능합니다.
요청
Header
주식주문(현금[V1_국내주식-001]) 정보 Element, 한글명, Type, Rquired, Length, Description
Element	한글명	Type	Required	Length	Description
content-type	컨텐츠타입	String	Y	40	application/json; charset=utf-8
authorization	접근토큰	String	Y	350	OAuth 토큰이 필요한 API 경우 발급한 Access token
일반고객(Access token 유효기간 1일, OAuth 2.0의 Client Credentials Grant 절차를 준용)
법인(Access token 유효기간 3개월, Refresh token 유효기간 1년, OAuth 2.0의 Authorization Code Grant 절차를 준용)
appkey	앱키	String	Y	36	한국투자증권 홈페이지에서 발급받은 appkey (절대 노출되지 않도록 주의해주세요.)
appsecret	앱시크릿키	String	Y	180	한국투자증권 홈페이지에서 발급받은 appkey (절대 노출되지 않도록 주의해주세요.)
personalseckey	고객식별키	String	N	180	[법인 필수] 제휴사 회원 관리를 위한 고객식별키
tr_id	거래ID	String	Y	13	FHKST01011801
tr_cont	연속 거래 여부	String	N	1	tr_cont를 이용한 다음조회 불가 API
custtype	고객 타입	String	Y	1	B : 법인
P : 개인
seq_no	일련번호	String	N	2	[법인 필수] 001
mac_address	맥주소	String	N	12	법인고객 혹은 개인고객의 Mac address 값
phone_number	핸드폰번호	String	N	12	[법인 필수] 제휴사APP을 사용하는 경우 사용자(회원) 핸드폰번호
ex) 01011112222 (하이픈 등 구분값 제거)
ip_addr	접속 단말 공인 IP	String	N	12	[법인 필수] 사용자(회원)의 IP Address
gt_uid	Global UID	String	N	32	[법인 전용] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
Query Parameter
주식주문(현금[V1_국내주식-001]) 정보 Element, 한글명, Type, Rquired, Length, Description
Element	한글명	Type	Required	Length	Description
FID_NEWS_OFER_ENTP_CODE	뉴스제공업체코드	String	Y	40	뉴스제공업체구분=>0:전체조회
FID_COND_MRKT_CLS_CODE	조건시장구분코드	String	Y	6	공백
FID_INPUT_ISCD	입력종목코드	String	Y	12	공백
FID_TITL_CNTT	제목내용	String	Y	132	공백
FID_INPUT_DATE_1	입력날짜1	String	Y	10	공백
FID_INPUT_HOUR_1	입력시간1	String	Y	10	공백
FID_RANK_SORT_CLS_CODE	순위정렬구분코드	String	Y	2	공백
FID_INPUT_SRNO	입력일련번호	String	Y	20	공백
FID_COND_SCR_DIV_CODE	조건화면분류코드	String	Y	5	화면번호:11801
응답
Header
주식주문(현금[V1_국내주식-001]) 정보 Element, 한글명, Type, Rquired, Length, Description
Element	한글명	Type	Required	Length	Description
content-type	컨텐츠타입	String	Y	40	application/json; charset=utf-8
tr_id	거래ID	String	Y	13	요청한 tr_id
tr_cont	연속 거래 여부	String	N	1	tr_cont를 이용한 다음조회 불가 API
gt_uid	Global UID	String	N	32	[법인 전용] 거래고유번호로 사용하므로 거래별로 UNIQUE해야 함
Body
주식주문(현금[V1_국내주식-001]) 정보 Element, 한글명, Type, Rquired, Length, Description
Element	한글명	Type	Required	Length	Description
rt_cd	성공 실패 여부	String	Y	1	
msg_cd	응답코드	String	Y	8	
msg1	응답메세지	String	Y	80	
output	응답상세	Object Array	Y		array
cntt_usiq_srno

내용조회용일련번호	String	Y	20	
news_ofer_entp_code

뉴스제공업체코드	String	Y	1	
data_dt

작성일자	String	Y	8	
data_tm

작성시간	String	Y	6	
hts_pbnt_titl_cntt

HTS공시제목내용	String	Y	400	
news_lrdv_code

뉴스대구분	String	Y	8	
dorg

자료원	String	Y	20	
iscd1

종목코드1	String	Y	9	
iscd2

종목코드2	String	Y	9	
iscd3

종목코드3	String	Y	9	
iscd4

종목코드4	String	Y	9	
iscd5

종목코드5	String	Y	9	
iscd6

종목코드6	String	Y	9	
iscd7

종목코드7	String	Y	9	
iscd8

종목코드8	String	Y	9	
iscd9

종목코드9	String	Y	9	
iscd10

종목코드10	String	Y	9	
kor_isnm1

한글종목명1	String	Y	40	
kor_isnm2

한글종목명2	String	Y	40	
kor_isnm3

한글종목명3	String	Y	40	
kor_isnm4

한글종목명4	String	Y	40	
kor_isnm5

한글종목명5	String	Y	40	
kor_isnm6

한글종목명6	String	Y	40	
kor_isnm7

한글종목명7	String	Y	40	
kor_isnm8

한글종목명8	String	Y	40	
kor_isnm9

한글종목명9	String	Y	40	
kor_isnm10

한글종목명10	String	Y	40	
예시
Request
Data Class (Python)
Data Class (Python)
from dataclasses import dataclass

@dataclass
class RequestHeader:
    content-type: str    #컨텐츠타입
    authorization: str    #접근토큰
    appkey: str    #앱키
    appsecret: str    #앱시크릿키
    personalseckey: Optional[str] = None    #고객식별키
    tr_id: str    #거래ID
    tr_cont: Optional[str] = None    #연속 거래 여부
    custtype: str    #고객 타입
    seq_no: Optional[str] = None    #일련번호
    mac_address: Optional[str] = None    #맥주소
    phone_number: Optional[str] = None    #핸드폰번호
    ip_addr: Optional[str] = None    #접속 단말 공인 IP
    gt_uid: Optional[str] = None    #Global UID

@dataclass
class RequestQueryParam:
    FID_NEWS_OFER_ENTP_CODE: str    #뉴스제공업체코드
    FID_COND_MRKT_CLS_CODE: str    #조건시장구분코드
    FID_INPUT_ISCD: str    #입력종목코드
    FID_TITL_CNTT: str    #제목내용
    FID_INPUT_DATE_1: str    #입력날짜1
    FID_INPUT_HOUR_1: str    #입력시간1
    FID_RANK_SORT_CLS_CODE: str    #순위정렬구분코드
    FID_INPUT_SRNO: str    #입력일련번호
    FID_COND_SCR_DIV_CODE: str    #조건화면분류코드

복사하기
Response
Data Class (Python)
Data Class (Python)
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ResponseHeader:
    content-type: str    #컨텐츠타입
    tr_id: str    #거래ID
    tr_cont: Optional[str] = None    #연속 거래 여부
    gt_uid: Optional[str] = None    #Global UID

@dataclass
class ResponseBody:
    rt_cd: str    #성공 실패 여부
    msg_cd: str    #응답코드
    msg1: str    #응답메세지
    output: List[ResponseBodyoutput] = field(default_factory=list)    #응답상세

@dataclass
class ResponseBodyoutput:
    cntt_usiq_srno: str    #내용조회용일련번호
    news_ofer_entp_code: str    #뉴스제공업체코드
    data_dt: str    #작성일자
    data_tm: str    #작성시간
    hts_pbnt_titl_cntt: str    #HTS공시제목내용
    news_lrdv_code: str    #뉴스대구분
    dorg: str    #자료원
    iscd1: str    #종목코드1
    iscd2: str    #종목코드2
    iscd3: str    #종목코드3
    iscd4: str    #종목코드4
    iscd5: str    #종목코드5
    iscd6: str    #종목코드6
    iscd7: str    #종목코드7
    iscd8: str    #종목코드8
    iscd9: str    #종목코드9
    iscd10: str    #종목코드10
    kor_isnm1: str    #한글종목명1
    kor_isnm2: str    #한글종목명2
    kor_isnm3: str    #한글종목명3
    kor_isnm4: str    #한글종목명4
    kor_isnm5: str    #한글종목명5
    kor_isnm6: str    #한글종목명6
    kor_isnm7: str    #한글종목명7
    kor_isnm8: str    #한글종목명8
    kor_isnm9: str    #한글종목명9
    kor_isnm10: str    #한글종목명10
