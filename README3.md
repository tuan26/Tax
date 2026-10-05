# Đào sâu vào 1 SSA “Tìm một workflow mà kế toán đang mất 60 phút và làm nó còn 10 phút.”

Được. Nếu chỉ chọn **một SSA (Smallest Sellable/Standalone Action)** cho sản phẩm hỗ trợ kế toán hộ kinh doanh, tôi sẽ không bắt đầu bằng “AI làm thuế”, cũng không bắt đầu bằng chatbot.

Tôi sẽ khoan rất sâu vào một workflow:

> **Từ một đống ảnh hóa đơn/chứng từ + thông tin giao dịch lộn xộn → tạo ra danh sách giao dịch đã chuẩn hóa, chỉ để kế toán kiểm tra ngoại lệ và bấm duyệt.**

Đây có khả năng biến một workflow **~60 phút → ~10–15 phút**.

## 1. 60 phút của kế toán thực sự biến mất ở đâu?

Hãy hình dung một hộ kinh doanh gửi trong ngày:

- 15 ảnh hóa đơn.
- 5 bill chuyển khoản.
- vài ảnh chụp màn hình.
- một số tin nhắn: “cái này tiền nhập hàng”, “hóa đơn này của hôm qua”.
- có ảnh gửi hai lần.
- có chứng từ thiếu ngày/số tiền.
- có một ảnh gửi nhầm.

Kế toán hiện tại không chỉ **nhập liệu**.

Họ phải làm chuỗi:

**Nhận → đọc → hiểu → phân loại → kiểm tra → đối chiếu → nhập → phát hiện vấn đề → hỏi lại → sửa.**

Giả sử 20 chứng từ:

| Hoạt động | Hiện tại |
|---|---:|
| Mở/tải/sắp xếp chứng từ | 8 phút |
| Đọc thông tin | 12 phút |
| Nhập dữ liệu | 15 phút |
| Phân loại | 8 phút |
| Kiểm tra thiếu/sai/trùng | 7 phút |
| Đối chiếu | 5 phút |
| Ghi chú/câu hỏi cần xử lý | 5 phút |
| **Tổng** | **~60 phút** |

Nếu sản phẩm chỉ OCR thì chúng ta chỉ giải quyết một phần của **12 + 15 phút**.

Không đủ mạnh.

---

# 2. SSA nên là gì?

Tôi sẽ định nghĩa SSA đầu tiên cực kỳ cụ thể:

> ### **20 chứng từ vào → 1 hàng chờ duyệt ra.**

Input:

**Ảnh / PDF / thông tin nhập tay**

↓

Hệ thống tự động:

**Extract**

↓

**Normalize**

↓

**Classify**

↓

**Match**

↓

**Validate**

↓

**Detect anomaly**

↓

Output:

### Approval Queue

Kế toán chỉ cần:

**✓ Duyệt**

hoặc

**⚠ Sửa/Xử lý**

Đây mới là sản phẩm.

Không phải OCR.

Không phải chatbot.

Không phải accounting software.

---

# 3. Trải nghiệm lý tưởng: 60 → 10 phút

Ví dụ hộ A gửi 20 chứng từ.

Hệ thống xử lý trước và đưa cho kế toán:

| # | Ngày | Loại | NCC | Số tiền | Status |
|---|---|---|---|---:|---|
| 01 | 05/10 | Mua hàng | ABC | 1.250k | ✅ |
| 02 | 05/10 | Điện | EVN | 820k | ✅ |
| 03 | 05/10 | Mua hàng | XYZ | 3.200k | ⚠ |
| 04 | 05/10 | Mua hàng | ABC | 1.250k | 🔴 Duplicate |
| … | | | | | |
| 20 | 05/10 | Vận chuyển | GHN | 450k | ✅ |

Kết quả:

**16 giao dịch**

> 🟢 High confidence  
> → kế toán review cực nhanh.

**3 giao dịch**

> 🟡 Need review

**1 giao dịch**

> 🔴 Duplicate

Kế toán không còn xử lý **20 items** ngang nhau.

Họ thực chất xử lý:

> **4 exceptions.**

Đây là thay đổi quan trọng nhất.

---

# 4. Đừng automate 60 phút. Hãy eliminate 50 phút.

Hai tư duy khác nhau.

### Tư duy thông thường

> Kế toán nhập dữ liệu → AI nhập nhanh hơn.

### Tư duy sản phẩm

> Tại sao kế toán phải nhìn vào 16 chứng từ hoàn toàn bình thường?

Do đó kiến trúc workflow nên là:

**Machine handles normal cases.**

**Human handles uncertainty.**

Hay:

> **AI làm 80%; kế toán chỉ xử lý 20% ngoại lệ.**

Đây chính là leverage.

---

# 5. Nhưng có một nguyên tắc sống còn: AI không được “đoán”

Đặc biệt với accounting.

Ví dụ AI thấy:

> Nhà cung cấp: ABC  
> Amount: 1.250.000  
> Date: mờ

Không được tự suy:

> 05/10/2026.

Thay vào đó:

**business_date: NULL**

**confidence: LOW**

**reason: Ngày chứng từ không đọc được**

→ Approval Queue.

Tương tự với tình huống:

> “anh ơi hóa đơn lúc nãy em gửi nhầm”

Không được coi tin nhắn là noise.

Nó phải:

**message**

→ tìm chứng từ liên quan

→ `possible_retraction`

→ transaction chuyển trạng thái

**NEED_REVIEW**

Đây chính là loại tình huống mà sản phẩm của bạn đã phát hiện cần xử lý cẩn thận. 

---

# 6. Tôi sẽ giới hạn SSA #1 còn nhỏ hơn nữa

Đừng làm tất cả hộ kinh doanh.

Chọn **một vertical**.

Ví dụ:

> **Quán ăn nhỏ**

và ban đầu chỉ giải quyết:

**Chi phí đầu vào.**

Input:

> hóa đơn mua nguyên liệu  
> hóa đơn điện/nước  
> vận chuyển  
> thuê mặt bằng  
> chi phí khác.

Chưa làm:

- inventory phức tạp
- payroll
- tax filing tự động
- báo cáo tài chính đầy đủ
- banking automation
- POS integration.

SSA trở thành:

> **“Biến chứng từ chi phí hằng ngày của một quán ăn thành sổ chi phí đã kiểm tra sơ bộ.”**

Cực kỳ dễ hiểu.

---

# 7. KPI quan trọng nhất không phải Accuracy

Đây là điểm tôi muốn thay đổi trong cách bạn nghĩ về pilot.

Đừng chỉ đo:

> OCR accuracy = 95%.

Có thể OCR 99% mà sản phẩm vẫn vô dụng.

North Star Metric nên là:

> ### **Accounting minutes / household / period**

Ví dụ baseline:

**62 phút**

Pilot:

**14 phút**

Target:

**≤10–15 phút**

Đồng thời đặt guardrails:

**Wrong auto-accept ≈ 0**

**Missing transaction ≈ 0**

Tức là chấp nhận:

> đưa nhiều item sang review

hơn là:

> tự động ghi sai.

---

# 8. Đây chính là nơi “Specific Knowledge” xuất hiện

Giả sử Google/OpenAI/Microsoft đều OCR tốt hơn bạn.

Không sao.

**OCR không phải moat.**

Moat nằm ở:

### Accounting workflow knowledge

Ví dụ hệ thống biết:

> chứng từ nào cần giữ  
> trường nào bắt buộc  
> giao dịch nào cần match  
> trường hợp nào phải hỏi lại  
> trường hợp nào có khả năng duplicate  
> trường hợp nào tuyệt đối không được tự quyết.

Sau 10.000 giao dịch, bạn bắt đầu sở hữu:

**Rule library**

+

**Exception patterns**

+

**Accounting workflow**

+

**Evaluation dataset**

Đó mới là **Specific Knowledge**.

---

# 9. Và đây là chỗ Naval xuất hiện rất rõ

Ban đầu:

### Accountant

1 người × 8h

↓

**Specific Knowledge**

Bạn hiểu cách họ xử lý chứng từ.

↓

**Code**

Bạn encode workflow đó.

↓

**AI**

Machine xử lý normal cases.

↓

**Leverage**

Một hệ thống có thể hỗ trợ:

10 hộ

→ 100

→ 1.000

→ 100.000 hộ.

Chi phí không tăng tuyến tính theo số kế toán.

↓

**Ownership**

Bạn sở hữu:

software + workflow + data model + rules + dataset.

↓

**Wealth**

Asset tiếp tục tạo value khi bạn không trực tiếp nhập từng chứng từ.

Đây gần như là ví dụ hoàn hảo của:

> **Productize Specific Knowledge.**

---

# 10. Nhưng trước khi code thêm, tôi sẽ làm một việc

Bạn đang ở thời điểm rất dễ mắc lỗi:

> **Có solution rồi → đi tìm problem phù hợp với solution.**

Hãy đảo lại.

Trong 2–3 buổi phỏng vấn kế toán, **không giới thiệu app trước**.

Ngồi cạnh họ và yêu cầu:

> “Chị làm thử cho em một hộ từ lúc nhận chứng từ đến lúc hoàn thành nhé.”

Bấm stopwatch.

Ghi lại từng action:

**00:00** mở Zalo  
**02:13** download ảnh  
**04:20** nhìn hóa đơn  
**05:10** mở Excel  
**06:03** nhập amount  
...  
**42:30** phát hiện thiếu hóa đơn  
**43:00** nhắn khách  
...

Sau 3–5 case, chúng ta sẽ có một **time map**.

Ví dụ:

**60 phút**

→ 12 phút collecting  
→ 18 phút data entry  
→ 7 phút classification  
→ 13 phút reconciliation  
→ 10 phút exceptions.

Lúc đó mới quyết định:

> **SSA nào đáng automate nhất.**

Có khả năng giả thuyết “60 → 10 phút” của chúng ta đúng.

Nhưng cũng có khả năng phát hiện:

> Nhập liệu chỉ mất 10 phút; **30 phút thực sự nằm ở việc đuổi khách bổ sung chứng từ**.

Nếu vậy, product direction phải thay đổi hoàn toàn.

---

# 11. Nếu là tôi, tuần này chỉ làm một experiment

Không thêm 20 API.

Không thêm dashboard.

Không thêm AI Agent.

Lấy:

**1 kế toán × 1 hộ × 1 kỳ thực**

và đo:

### BEFORE

`Raw documents`

→ stopwatch

→ `Completed accounting records`

### AFTER

Cho chạy qua prototype hiện tại:

`Raw documents`

→ system

→ accountant review

→ `Completed accounting records`

So sánh:

> **Time:** 62 → ?  
> **Manual actions:** 47 → ?  
> **Exceptions:** ?  
> **Wrong suggestions:** ?  
> **Missing:** ?  
> **Accountant confidence:** ?

Nếu kết quả là:

> **62 phút → 13 phút**

thì tôi sẽ **dừng việc mở rộng feature**.

Lấy thêm:

**2 accountant × 3 households × 2 periods.**

Nếu vẫn giữ được khoảng:

> **50–80% time reduction**

thì bạn đã tìm thấy thứ giá trị hơn rất nhiều so với một ý tưởng startup:

## Một workflow đã được chứng minh có thể productize.

Khi đó câu hỏi tiếp theo không còn là **“App nên có chức năng gì?”**, mà là:

> **“Một kế toán sẵn sàng trả bao nhiêu tiền để lấy lại 40–50 phút này, và với 100 hộ thì ROI của họ là bao nhiêu?”**

Đó là điểm tôi sẽ chuyển từ **technical pilot → business validation**.

# Tôi muốn xây dựng 1 team cung cấp giải pháp nhằm giải bài toán tự động cho user thường hoặc doanh nghiệp
Được, và thực ra **không mạnh code không phải điểm chặn lớn nhất** cho hướng này. Nếu vai trò của bạn là founder/solution lead, năng lực quan trọng hơn là **tìm đúng pain point → thiết kế workflow → chứng minh ROI → tổ chức người/AI để build**.

Tôi sẽ không định vị team là “công ty AI”. Tôi sẽ định vị rất cụ thể:

> **Automation Solution Team — tìm những công việc đang mất 60 phút và biến chúng thành 10 phút bằng AI + automation + software.**

Đây có thể trở thành hướng “Productize Yourself” rất phù hợp với bạn.

## 1. Vai trò của bạn không cần là coder

Bạn nên đứng ở vị trí:

**Problem / Product / Solution Owner**

Bạn chịu trách nhiệm chuỗi:

**User pain → workflow → requirement → solution → ROI → productization**

Developer chịu:

**Architecture → implementation → deployment → operation**

AI giúp cả hai phía tăng leverage.

Ví dụ khách nói:

> “Mỗi cuối tháng tôi mất 2 ngày tổng hợp 20 file Excel.”

Bạn phải có khả năng đi từ:

`Pain`
→ quan sát workflow
→ tìm bottleneck
→ xác định phần có thể automate
→ thiết kế To-Be
→ tính ROI
→ prototype
→ đưa Dev build
→ đo Before/After.

Đó là **Specific Knowledge** rất có giá trị.

---

# 2. Tôi sẽ xây team cực nhỏ trước

Không cần lập team 10 người.

Ban đầu:

| Role | Người | Trách nhiệm |
|---|---:|---|
| **Solution/BA/Product** | **Bạn** | Discovery, workflow, requirement, khách hàng |
| **AI/Full-stack Engineer** | 1 | Build solution |
| **Automation Engineer** | 1 | n8n/Power Automate/API/integration |
| Designer/QA/Infra | part-time/AI | Khi cần |

Thậm chí MVP:

> **Bạn + 1 technical co-builder + AI**

là đủ.

Người đầu tiên tôi tìm **không phải junior coder**.

Hãy tìm một người kiểu:

> **AI Full-stack / Solution Engineer**

có khả năng tự đi từ:

API → database → LLM → automation → frontend → deploy.

Bạn bổ sung cho họ thứ họ thường thiếu:

**Business × Customer × Requirement × Japanese × Product thinking.**

Hai bên rất complementary.

---

# 3. Đừng bán “AI”. Bán kết quả

Sai:

> “Team chúng tôi cung cấp AI Agent, RAG, OCR, n8n...”

Khách hàng bình thường không quan tâm.

Định vị tốt hơn:

> **Chúng tôi tìm các workflow thủ công đang tiêu tốn 30–120 phút mỗi ngày và tự động hóa chúng xuống còn 5–20 phút.**

Ví dụ:

**Kế toán**

60 phút xử lý chứng từ  
→ 10 phút review.

**Sales**

2 giờ tổng hợp lead  
→ 15 phút.

**HR**

3 giờ screening CV  
→ 30 phút review.

**BA**

2 giờ requirement → US/QA  
→ 20 phút review.

**SME**

Nhận order Zalo → Excel → invoice → report  
→ một workflow tự động.

Bạn đang bán:

> **Hours Saved**

chứ không phải token hay model.

---

# 4. Business model ban đầu: Service → Productized Service → Product

Đây là phần cực kỳ quan trọng.

Đừng nhảy ngay:

> SaaS.

Hãy đi:

### Stage 1 — Automation Service

Khách:

> “Tôi có vấn đề X.”

Bạn phân tích và làm riêng cho họ.

Ví dụ:

**10–30 triệu/project**.

Mục tiêu chưa phải scale.

Mục tiêu là lấy:

**Knowledge + Problems + Cases + Money.**

---

### Stage 2 — Productized Service

Sau khoảng 10 project bạn nhận ra:

> 6 khách đều có cùng một vấn đề.

Ví dụ:

`Invoice → OCR → classify → Excel/accounting system`

Thay vì custom lại:

**80% standard + 20% customization**

và bán:

> **Gói tự động hóa xử lý chứng từ**

---

### Stage 3 — Product

Khi workflow đã đủ rõ:

**95% standard**

↓

SaaS

↓

Khách tự đăng ký.

Lúc này:

**Service knowledge → Software asset.**

Đây chính là Naval.

---

# 5. Team của bạn đồng thời phải là một “Knowledge Machine”

Đây mới là phần tôi đặc biệt khuyến khích.

Mỗi project không chỉ kiếm tiền.

Nó phải tạo ra **tài sản tri thức**.

Ví dụ Project #01:

> Invoice Automation

sau khi hoàn thành phải thu được:

**Case Study #01**  
**Workflow Pattern #01**  
**Prompt #01–10**  
**OCR pipeline**  
**Validation Rules**  
**Reusable Components**  
**ROI Calculator**  
**Demo**  
**Article/Video**

Project #02 tái sử dụng 30%.

Project #10 tái sử dụng 70%.

Project #30 có thể trở thành product.

Như vậy:

**Client work → Knowledge → IP → Content → Reputation → Leads → More client work**

Bạn tạo được một flywheel.

---

# 6. Đây cũng là cách xây thương hiệu

Đừng xây thương hiệu bằng cách đăng:

> “10 công cụ AI tuyệt vời năm 2026.”

Có hàng nghìn người làm rồi.

Hãy đăng **case thực tế**:

> “Một kế toán mất 63 phút xử lý 22 chứng từ. Chúng tôi giảm xuống 14 phút như thế nào?”

Hoặc:

> “Chúng tôi thử dùng AI đọc 500 hóa đơn và đây là 7 trường hợp AI tuyệt đối không nên tự quyết.”

Hoặc:

> “Workflow này tiết kiệm 37 giờ/tháng nhưng chúng tôi quyết định KHÔNG dùng AI Agent.”

Đó là **Specific Knowledge được public hóa**.

Sau 30–50 case, người khác bắt đầu associate:

> **Automation business process → team của bạn.**

Đây chính là Luck #4 mà chúng ta vừa nói:

**Reputation makes opportunities find you.**

---

# 7. Nhưng tôi khuyên bạn tránh một sai lầm lớn

Đừng bắt đầu bằng:

> “Chúng ta nhận mọi bài toán automation.”

Quá rộng.

Bạn sẽ trở thành outsourcing company.

Nên bắt đầu bằng một **wedge**.

Ví dụ tôi khá thích:

> ### AI Automation cho back-office SME

và chỉ tập trung:

**Accounting / Documents / Excel / Email / Approval / Reporting**

Tại sao?

Các workflow này thường:

- repetitive
- measurable
- nhiều manual work
- input/output tương đối rõ
- ROI dễ tính
- rất phù hợp AI + automation.

Sau này mới mở rộng.

---

# 8. Bạn nên học technical đến đâu?

Bạn **không cần trở thành software engineer**.

Nhưng cũng không thể hoàn toàn không hiểu technical.

Mục tiêu của bạn là **technical literacy**, không phải coding mastery.

Bạn nên hiểu được:

`API`
`Webhook`
`JSON`
`Database`
`OAuth`
`LLM API`
`RAG`
`OCR`
`Agent`
`Workflow automation`
`Cloud`
`Docker`
`Git`
`Logging`
`Security`

đến mức Developer nói:

> Webhook → API → Queue → OCR → LLM → DB

bạn hiểu hệ thống đang làm gì, đặt được câu hỏi đúng và nhận ra risk.

Còn việc implement production-quality code → **Engineer**.

AI có thể giúp bạn prototype đủ nhiều để nói chuyện với Engineer rất hiệu quả.

---

# 9. Tôi sẽ đặt mục tiêu 12 tháng đầu như thế này

Không phải:

> Thành lập công ty AI.

Mà là:

### **100 → 10 Mission**

> **Tìm 10 workflow thực tế có thể giảm ≥70% thời gian xử lý.**

Ví dụ:

**#01 Accounting:** 60 → 12 phút  
**#02 BA:** 120 → 25 phút  
**#03 Sales:** 45 → 8 phút  
...  
**#10**

Trong 10 case đó tìm:

> **1 pattern xuất hiện ≥3 lần.**

Pattern đó trở thành ứng viên Product #1.

---

# 10. Và tôi nghĩ bạn nên bắt đầu ngay từ dự án kế toán

Đừng coi sản phẩm kế toán hiện tại chỉ là một startup idea.

Hãy coi nó là:

> **Automation Lab #001**

Mission:

### `Accounting 60 → 10`

Bạn:

**Discovery / BA / Product**

↓

Tìm 2–3 kế toán

↓

Quan sát workflow thực

↓

Đo từng bước

↓

Vẽ **As-Is**

↓

Chọn bottleneck

↓

Thiết kế **To-Be**

↓

Engineer + AI build

↓

Pilot

↓

Đo Before/After

↓

Case Study

↓

Publish knowledge

↓

Tìm khách hàng tiếp theo.

Nếu thất bại, bạn vẫn thu được **domain knowledge + methodology + case study + reusable technology**.

Nếu thành công, bạn có **Product #001**.

---

## Flywheel dài hạn của bạn

Tôi muốn bạn hình dung business tương lai không phải là một software house:

**① Find painful workflow**

↓  

**② 60 → 10**

↓  

**③ Customer pays**

↓  

**④ Extract knowledge**

↓  

**⑤ Build reusable components**

↓  

**⑥ Publish case study**

↓  

**⑦ Build reputation**

↓  

**⑧ More customers**

↓  

**⑨ Discover repeated patterns**

↓  

**⑩ Turn pattern into SaaS**

↺

Đây mới là điểm giao nhau rất đẹp giữa mục tiêu của bạn và Naval:

> **Specific Knowledge × Accountability × Code/AI Leverage × Ownership**

Và với bạn, tôi sẽ **không dành 6 tháng tới để học Python rồi mới bắt đầu**. Tôi sẽ dành thời gian đó để trở thành người cực giỏi ở **Problem Discovery + AI Solution Design + Productization**, đồng thời tìm **một technical co-builder mạnh**. Khả năng BA của bạn lúc đó không còn là điểm yếu so với coder; nó trở thành một nửa của cặp năng lực cần thiết để xây business này.
