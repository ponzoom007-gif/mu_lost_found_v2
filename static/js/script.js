document.addEventListener("DOMContentLoaded", function () {
    const itemTypeRadios = document.querySelectorAll("input[name='item_type']");
    const custodyWrapper = document.getElementById("custody_wrapper");
    const radioDropped = document.getElementById("custody_dropped");
    const radioKeep = document.getElementById("custody_keep");
    const dropSection = document.getElementById("drop_section");
    const contactSection = document.getElementById("contact_section");
    const dropDetailInput = document.getElementById("drop_location_detail");
    const contactInput = document.getElementById("contact_info");
    const contactLabel = document.getElementById("contact_label");
    const verificationLabel = document.getElementById("verification_label");
    const verificationHint = document.getElementById("verification_hint");
    const verificationInput = document.getElementById("verification_question");

    function updateFormForType() {
        const selectedType = document.querySelector("input[name='item_type']:checked");
        const isLost = selectedType && selectedType.value === "lost";
        const labelFound = document.getElementById("label_found");
        const labelLost = document.getElementById("label_lost");

        if (isLost) {
            // โหมดทำของหาย (Lost)
            if (labelFound) labelFound.classList.remove("selected-found");
            if (labelLost) labelLost.classList.add("selected-lost");

            if (custodyWrapper) custodyWrapper.style.display = "none";
            if (dropSection) dropSection.style.display = "none";
            if (contactSection) contactSection.style.display = "block";

            if (dropDetailInput) dropDetailInput.removeAttribute("required");
            if (contactInput) contactInput.setAttribute("required", "required");
            if (contactLabel) contactLabel.innerText = "ช่องทางการติดต่อคุณ (ผู้ทำของหาย) *";

            if (verificationLabel) verificationLabel.innerText = "🔍 จุดสังเกตเฉพาะที่จำได้ (ถ้ามี เพื่อใช้ตรวจสอบเมื่อมีคนพบ)";
            if (verificationHint) verificationHint.innerText = "* ข้อมูลนี้จะช่วยให้ผู้ที่เก็บได้ช่วยยืนยันว่าเป็นของของคุณจริง";
            if (verificationInput) verificationInput.placeholder = "เช่น 'มีรอยขีดข่วนด้านหลัง', 'หน้าจอติดสติ๊กเกอร์สีฟ้า'";
        } else {
            // โหมดเก็บของได้ (Found)
            if (labelFound) labelFound.classList.add("selected-found");
            if (labelLost) labelLost.classList.remove("selected-lost");

            if (custodyWrapper) custodyWrapper.style.display = "block";
            if (contactLabel) contactLabel.innerText = "ช่องทางการติดต่อคุณ (ผู้เก็บได้) *";

            if (verificationLabel) verificationLabel.innerText = "🛡️ คำถามยืนยันความเป็นเจ้าของ (Anti-Spoofing Question)";
            if (verificationHint) verificationHint.innerText = "* ผู้ที่มาขอรับของจะต้องตอบคำถามนี้ให้ถูกต้อง เพื่อป้องกันมิจฉาชีพสวมรอย";
            if (verificationInput) verificationInput.placeholder = "เช่น 'กระเป๋ามีบัตรอะไรอยู่ข้างในบ้าง?' หรือ 'เคสข้างหลังมีสติ๊กเกอร์อะไร?'";

            toggleCustodySections();
        }
    }

    function toggleCustodySections() {
        const selectedType = document.querySelector("input[name='item_type']:checked");
        if (selectedType && selectedType.value === "lost") return;
        if (!radioDropped || !radioKeep) return;

        if (radioDropped.checked) {
            if (dropSection) dropSection.style.display = "block";
            if (contactSection) contactSection.style.display = "none";
            if (dropDetailInput) dropDetailInput.setAttribute("required", "required");
            if (contactInput) contactInput.removeAttribute("required");
        } else if (radioKeep.checked) {
            if (dropSection) dropSection.style.display = "none";
            if (contactSection) contactSection.style.display = "block";
            if (contactInput) contactInput.setAttribute("required", "required");
            if (dropDetailInput) dropDetailInput.removeAttribute("required");
        }
    }

    if (itemTypeRadios.length > 0) {
        itemTypeRadios.forEach(radio => radio.addEventListener("change", updateFormForType));
    }

    if (radioDropped && radioKeep) {
        radioDropped.addEventListener("change", toggleCustodySections);
        radioKeep.addEventListener("change", toggleCustodySections);
    }

    // เรียกทำงานครั้งแรกตอนโหลดหน้า
    if (itemTypeRadios.length > 0) {
        updateFormForType();
    } else if (radioDropped && radioKeep) {
        toggleCustodySections();
    }

    // กำหนดเวลาเริ่มต้นแบบ Local Timezone
    const dateInput = document.getElementById("incident_date");
    const timeInput = document.getElementById("incident_time");

    if (dateInput && timeInput && !dateInput.value) {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, "0");
        const day = String(now.getDate()).padStart(2, "0");
        const hours = String(now.getHours()).padStart(2, "0");
        const minutes = String(now.getMinutes()).padStart(2, "0");

        dateInput.value = `${year}-${month}-${day}`;
        timeInput.value = `${hours}:${minutes}`;
    }

    const searchInput = document.getElementById("liveSearchInput");
    const facultyFilter = document.getElementById("liveFacultyFilter");
    const typeFilter = document.getElementById("liveTypeFilter");
    const dateFilter = document.getElementById("liveDateFilter");
    const resetBtn = document.getElementById("btnResetFilter");
    const noResultsMsg = document.getElementById("noLiveResults");
    const itemCards = document.querySelectorAll("#itemsContainer .item-card");

    function applyLiveFilter() {
        const searchText = searchInput ? searchInput.value.toLowerCase().trim() : "";
        const selectedFaculty = facultyFilter ? facultyFilter.value : "";
        const selectedType = typeFilter ? typeFilter.value : "";
        const selectedDate = dateFilter ? dateFilter.value : "";

        let visibleCount = 0;

        itemCards.forEach(card => {
            const title = card.getAttribute("data-title") || "";
            const desc = card.getAttribute("data-desc") || "";
            const location = card.getAttribute("data-location") || "";
            const type = card.getAttribute("data-type") || "";
            const itemDate = card.getAttribute("data-date") || "";

            const matchSearch = searchText === "" || title.includes(searchText) || desc.includes(searchText);
            const matchFaculty = selectedFaculty === "" || location === selectedFaculty;
            const matchType = selectedType === "" || type === selectedType;
            // กรองประกาศตั้งแต่วันที่เลือกเป็นต้นมาจนถึงปัจจุบัน
            const matchDate = selectedDate === "" || (itemDate && itemDate >= selectedDate);

            if (matchSearch && matchFaculty && matchType && matchDate) {
                card.style.display = "flex";
                visibleCount++;
            } else {
                card.style.display = "none";
            }
        });

        if (noResultsMsg) {
            if (visibleCount === 0 && itemCards.length > 0) {
                noResultsMsg.style.display = "block";
            } else {
                noResultsMsg.style.display = "none";
            }
        }
    }

    if (searchInput) searchInput.addEventListener("input", applyLiveFilter);
    if (facultyFilter) facultyFilter.addEventListener("change", applyLiveFilter);
    if (typeFilter) typeFilter.addEventListener("change", applyLiveFilter);
    if (dateFilter) dateFilter.addEventListener("change", applyLiveFilter);

    if (resetBtn) {
        resetBtn.addEventListener("click", function () {
            if (searchInput) searchInput.value = "";
            if (facultyFilter) facultyFilter.value = "";
            if (typeFilter) typeFilter.value = "";
            if (dateFilter) dateFilter.value = "";
            applyLiveFilter();
        });
    }

    // ระบบเมนู 3 ขีด (Hamburger & User Dropdown Menu)
    const navMenuBtn = document.getElementById("navMenuBtn");
    const menuDropdown = document.getElementById("menuDropdown");
    const menuDropdownWrapper = document.getElementById("menuDropdownWrapper");

    if (navMenuBtn && menuDropdown) {
        navMenuBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            const isOpen = menuDropdown.classList.toggle("show");
            navMenuBtn.classList.toggle("active", isOpen);
            navMenuBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });

        // ปิดเมนูอัตโนมัติเมื่อคลิกนอกเมนู
        document.addEventListener("click", function (e) {
            if (menuDropdownWrapper && !menuDropdownWrapper.contains(e.target)) {
                menuDropdown.classList.remove("show");
                navMenuBtn.classList.remove("active");
                navMenuBtn.setAttribute("aria-expanded", "false");
            }
        });

        // ปิดเมนูเมื่อคลิกเลือกลิงก์ภายในเมนู
        menuDropdown.querySelectorAll("a").forEach(link => {
            link.addEventListener("click", function () {
                menuDropdown.classList.remove("show");
                navMenuBtn.classList.remove("active");
                navMenuBtn.setAttribute("aria-expanded", "false");
            });
        });
    }
});

// ฟังก์ชันสลับแสดง/ซ่อนรหัสผ่าน เพื่อป้องกันการพิมพ์ผิดก่อนกดส่ง
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    if (input.type === "password") {
        input.type = "text";
        if (btn) {
            btn.innerText = "🙈";
            btn.title = "ซ่อนรหัสผ่าน";
            btn.setAttribute("aria-label", "ซ่อนรหัสผ่าน");
        }
    } else {
        input.type = "password";
        if (btn) {
            btn.innerText = "👁️";
            btn.title = "แสดงรหัสผ่าน";
            btn.setAttribute("aria-label", "แสดงรหัสผ่าน");
        }
    }
}

