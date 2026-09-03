document.addEventListener("DOMContentLoaded", function () {
    // ----------------- TYPE TOGGLE & REPORT FORM ----------------- //
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

    if (itemTypeRadios.length > 0) {
        updateFormForType();
    } else if (radioDropped && radioKeep) {
        toggleCustodySections();
    }

    // วันที่และเวลาเริ่มต้นอัตโนมัติ
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

    // ----------------- LIVE FILTER & SEARCH ----------------- //
    const searchInput = document.getElementById("liveSearchInput");
    const facultyFilter = document.getElementById("liveFacultyFilter");
    const typeFilter = document.getElementById("liveTypeFilter");
    const dateFilter = document.getElementById("liveDateFilter");
    const resetBtn = document.getElementById("btnResetFilter");
    const noResultsMsg = document.getElementById("noLiveResults");
    const itemCards = document.querySelectorAll("#itemsContainer .item-card");
    const categoryChips = document.querySelectorAll(".category-chip");
    let activeCategory = "";

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
            const category = card.getAttribute("data-category") || "";
            const type = card.getAttribute("data-type") || "";
            const itemDate = card.getAttribute("data-date") || "";

            const matchSearch = searchText === "" || title.includes(searchText) || desc.includes(searchText);
            const matchFaculty = selectedFaculty === "" || location === selectedFaculty;
            const matchCategory = activeCategory === "" || category === activeCategory;
            const matchType = selectedType === "" || type === selectedType;
            const matchDate = selectedDate === "" || (itemDate && itemDate >= selectedDate);

            if (matchSearch && matchFaculty && matchCategory && matchType && matchDate) {
                card.style.display = "flex";
                visibleCount++;
            } else {
                card.style.display = "none";
            }
        });

        if (noResultsMsg) {
            noResultsMsg.style.display = (visibleCount === 0 && itemCards.length > 0) ? "block" : "none";
        }
    }

    if (categoryChips.length > 0) {
        categoryChips.forEach(chip => {
            chip.addEventListener("click", function () {
                categoryChips.forEach(c => c.classList.remove("active"));
                this.classList.add("active");
                activeCategory = this.getAttribute("data-category") || "";
                applyLiveFilter();
            });
        });
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
            activeCategory = "";
            categoryChips.forEach((c, idx) => {
                c.classList.toggle("active", idx === 0);
            });
            applyLiveFilter();
        });
    }

    // ----------------- MOBILE DRAWER & DESKTOP MENU ----------------- //
    const mobileDrawer = document.getElementById("mobileDrawer");
    const drawerBackdrop = document.getElementById("drawerBackdrop");
    const drawerOpenBtn = document.getElementById("mobileDrawerOpenBtn");
    const drawerCloseBtn = document.getElementById("mobileDrawerCloseBtn");
    const mobileBottomProfileBtn = document.getElementById("mobileBottomProfileBtn");

    function openDrawer() {
        if (mobileDrawer) mobileDrawer.classList.add("open");
        if (drawerBackdrop) drawerBackdrop.classList.add("show");
        document.body.style.overflow = "hidden";
    }

    function closeDrawer() {
        if (mobileDrawer) mobileDrawer.classList.remove("open");
        if (drawerBackdrop) drawerBackdrop.classList.remove("show");
        document.body.style.overflow = "";
    }

    if (drawerOpenBtn) drawerOpenBtn.addEventListener("click", openDrawer);
    if (mobileBottomProfileBtn) mobileBottomProfileBtn.addEventListener("click", openDrawer);
    if (drawerCloseBtn) drawerCloseBtn.addEventListener("click", closeDrawer);
    if (drawerBackdrop) drawerBackdrop.addEventListener("click", closeDrawer);

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closeDrawer();
    });

    // Desktop Dropdown
    const desktopUserBtn = document.getElementById("desktopUserBtn");
    const desktopDropdown = document.getElementById("desktopDropdown");
    if (desktopUserBtn && desktopDropdown) {
        desktopUserBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            desktopDropdown.classList.toggle("show");
        });
        document.addEventListener("click", function (e) {
            if (!desktopUserBtn.contains(e.target) && !desktopDropdown.contains(e.target)) {
                desktopDropdown.classList.remove("show");
            }
        });
    }

    // ----------------- 5. REAL-TIME PASSWORD MATCH VALIDATION ----------------- //
    const pwInput = document.getElementById("password");
    const confirmPwInput = document.getElementById("confirm_password");
    const pwMatchMsg = document.getElementById("passwordMatchMsg");
    const registerSubmitBtn = document.getElementById("btnRegisterSubmit");

    function validatePasswordMatch() {
        if (!pwInput || !confirmPwInput || !pwMatchMsg) return;

        const pwVal = pwInput.value;
        const confirmVal = confirmPwInput.value;

        if (!confirmVal && !pwVal) {
            pwMatchMsg.style.display = "none";
            if (registerSubmitBtn) registerSubmitBtn.disabled = false;
            return;
        }

        if (confirmVal.length > 0) {
            pwMatchMsg.style.display = "block";
            if (pwVal === confirmVal) {
                pwMatchMsg.className = "password-match-indicator match-success";
                pwMatchMsg.innerHTML = "<span>✓ รหัสผ่านตรงกันเรียบร้อยแล้ว</span>";
                if (registerSubmitBtn) registerSubmitBtn.disabled = false;
            } else {
                pwMatchMsg.className = "password-match-indicator match-error";
                pwMatchMsg.innerHTML = "<span>⚠️ รหัสผ่านยืนยันไม่ตรงกับรหัสผ่านแรก</span>";
                if (registerSubmitBtn) registerSubmitBtn.disabled = true;
            }
        } else {
            pwMatchMsg.style.display = "none";
            if (registerSubmitBtn) registerSubmitBtn.disabled = false;
        }
    }

    if (pwInput && confirmPwInput) {
        pwInput.addEventListener("input", validatePasswordMatch);
        confirmPwInput.addEventListener("input", validatePasswordMatch);
    }

    // ----------------- 3. INSTANT IMAGE PREVIEW & FILE VALIDATION ----------------- //
    const imageInputs = document.querySelectorAll(".image-file-input, input[type='file']");
    const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
    const ALLOWED_EXTS = ["png", "jpg", "jpeg", "webp", "heic", "heif", "jfif"];

    imageInputs.forEach(input => {
        input.addEventListener("change", function () {
            const previewBox = document.getElementById(`preview_${this.id}`);
            const file = this.files[0];

            if (!file) {
                if (previewBox) {
                    previewBox.style.display = "none";
                    previewBox.innerHTML = "";
                }
                return;
            }

            // Check file size
            if (file.size > MAX_FILE_SIZE) {
                alert(`⚠️ ไฟล์รูปภาพมีขนาด ${(file.size / (1024 * 1024)).toFixed(1)} MB ซึ่งเกินขีดจำกัด 5 MB\nกรุณาเลือกรูปภาพที่มีขนาดไม่เกิน 5 MB`);
                this.value = "";
                if (previewBox) {
                    previewBox.style.display = "none";
                    previewBox.innerHTML = "";
                }
                return;
            }

            // Check extension
            const ext = file.name.split('.').pop().toLowerCase();
            if (!ALLOWED_EXTS.includes(ext)) {
                alert(`⚠️ ชนิดไฟล์ .${ext} ไม่ได้รับการรองรับ\nระบบรองรับเฉพาะรูปภาพสกุล PNG, JPG, JPEG, WEBP และ HEIC`);
                this.value = "";
                if (previewBox) {
                    previewBox.style.display = "none";
                    previewBox.innerHTML = "";
                }
                return;
            }

            // Generate thumbnail preview
            if (previewBox && (file.type.startsWith("image/") || ext === "webp" || ext === "png" || ext === "jpg" || ext === "jpeg")) {
                const reader = new FileReader();
                reader.onload = function (e) {
                    previewBox.style.display = "flex";
                    previewBox.innerHTML = `
                        <div class="preview-card">
                            <img src="${e.target.result}" alt="Preview" class="preview-thumb">
                            <div class="preview-meta">
                                <span class="preview-filename">${file.name}</span>
                                <span class="preview-size">${(file.size / 1024).toFixed(1)} KB</span>
                            </div>
                            <button type="button" class="btn-remove-preview" title="ลบรูป">&times;</button>
                        </div>
                    `;
                    const removeBtn = previewBox.querySelector(".btn-remove-preview");
                    if (removeBtn) {
                        removeBtn.addEventListener("click", function () {
                            input.value = "";
                            previewBox.style.display = "none";
                            previewBox.innerHTML = "";
                        });
                    }
                };
                reader.readAsDataURL(file);
            }
        });
    });
});

// ฟังก์ชันสลับแสดง/ซ่อนรหัสผ่าน
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    if (input.type === "password") {
        input.type = "text";
        if (btn) {
            btn.innerText = "🙈";
            btn.title = "ซ่อนรหัสผ่าน";
        }
    } else {
        input.type = "password";
        if (btn) {
            btn.innerText = "👁️";
            btn.title = "แสดงรหัสผ่าน";
        }
    }
}

// 4. ฟังก์ชันคัดลอกลิงก์หน้าปัจจุบัน
function copyCurrentPageUrl(btn) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(window.location.href).then(() => {
            const originalHtml = btn.innerHTML;
            btn.innerHTML = "<span>✓ คัดลอกสำเร็จ!</span>";
            btn.style.background = "#10B981";
            btn.style.color = "white";
            btn.style.borderColor = "#059669";
            setTimeout(() => {
                btn.innerHTML = originalHtml;
                btn.style.background = "";
                btn.style.color = "";
                btn.style.borderColor = "";
            }, 2000);
        }).catch(() => {
            prompt("คัดลอกลิงก์ด้านล่างนี้ได้เลยครับ:", window.location.href);
        });
    } else {
        prompt("คัดลอกลิงก์ด้านล่างนี้ได้เลยครับ:", window.location.href);
    }
}

