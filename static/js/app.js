// Global Variables
let projectsCache = [];
let posCache = [];
let currentProjectId = null;
let currentPOId = null;
let currentProjectRightAssignment = "ไม่ได้โอนสิทธิ์";

// ----------------------------------------------------
// AUTHENTICATION FLOWS & JWT SECURITY (V5)
// ----------------------------------------------------
function getToken() {
    return localStorage.getItem("access_token");
}

function getHeaders(contentType = "application/json") {
    const token = getToken();
    const headers = {};
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }
    if (contentType) {
        headers["Content-Type"] = contentType;
    }
    return headers;
}

// Wrapper for Fetch API to automatically inject JWT token & handle 401/403 errors
async function secureFetch(url, options = {}) {
    options.headers = Object.assign({}, options.headers, getHeaders(options.body instanceof FormData ? null : "application/json"));
    
    try {
        const response = await fetch(url, options);
        if (response.status === 401) {
            console.warn("Unauthorized access detected (401). Redirecting to login...");
            handleLogout();
            throw new Error("Session expired. Please log in again.");
        }
        if (response.status === 403) {
            const errData = await response.clone().json().catch(() => ({}));
            // If it's a suspension error (not just standard 403 forbidden role block)
            if (errData.detail && errData.detail.includes("ระงับการใช้งาน")) {
                alert(errData.detail);
                handleLogout();
            }
            return response;
        }
        return response;
    } catch (err) {
        console.error("fetch error:", err);
        throw err;
    }
}

// Loader overlays (V5 Render Free Tier recovery helper)
function showLoading(text = "กำลังปลุกเซิร์ฟเวอร์คลาวด์ กรุณารอประมาณ 1 นาที...") {
    const overlay = document.getElementById("loading-overlay");
    const txt = document.getElementById("loading-text");
    if (overlay && txt) {
        txt.innerText = text;
        overlay.classList.remove("hidden");
    }
}

function hideLoading() {
    const overlay = document.getElementById("loading-overlay");
    if (overlay) {
        overlay.classList.add("hidden");
    }
}

// Forget password modal functions
function openForgetPasswordModal() {
    document.getElementById("forget-password-modal").classList.remove("hidden");
}

function closeForgetPasswordModal() {
    document.getElementById("forget-password-modal").classList.add("hidden");
}

// Toggle between Login and Register Cards
function toggleAuthCard(card) {
    const loginCard = document.getElementById("login-card");
    const registerCard = document.getElementById("register-card");
    if (card === "login") {
        loginCard.classList.remove("hidden");
        registerCard.classList.add("hidden");
    } else {
        loginCard.classList.add("hidden");
        registerCard.classList.remove("hidden");
    }
}

// Handle login submissions
async function handleLogin(event) {
    event.preventDefault();
    const usernameVal = document.getElementById("login-username").value.trim();
    const passwordVal = document.getElementById("login-password").value;
    
    showLoading("กำลังยืนยันข้อมูลและปลุกเซิร์ฟเวอร์คลาวด์ กรุณารอประมาณ 1 นาที...");
    try {
        const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: usernameVal, password: passwordVal })
        });
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง");
        }
        
        const data = await response.json();
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("current_user", JSON.stringify(data.user));
        
        document.getElementById("login-username").value = "";
        document.getElementById("login-password").value = "";
        
        checkAuthStatus();
    } catch (error) {
        console.error("Login error:", error);
        alert(error.message);
    } finally {
        hideLoading();
    }
}

// Handle registration submissions
async function handleRegister(event) {
    event.preventDefault();
    const fullnameVal = document.getElementById("register-fullname").value.trim();
    const usernameVal = document.getElementById("register-username").value.trim();
    const passwordVal = document.getElementById("register-password").value;
    
    showLoading("กำลังบันทึกข้อมูลการสมัครสมาชิกและปลุกเซิร์ฟเวอร์คลาวด์ กรุณารอประมาณ 1 นาที...");
    try {
        const response = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fullname: fullnameVal, username: usernameVal, password: passwordVal })
        });
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "ไม่สามารถสมัครสมาชิกได้");
        }
        
        alert("สมัครสมาชิกสำเร็จ! ย้อนกลับไปหน้าล็อกอินเพื่อเข้าสู่ระบบ");
        
        document.getElementById("register-fullname").value = "";
        document.getElementById("register-username").value = "";
        document.getElementById("register-password").value = "";
        
        toggleAuthCard("login");
    } catch (error) {
        console.error("Register error:", error);
        alert(error.message);
    } finally {
        hideLoading();
    }
}

// Logout session
function handleLogout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("current_user");
    
    document.getElementById("auth-container").classList.remove("hidden");
    document.getElementById("app-container").classList.add("hidden");
    
    toggleAuthCard("login");
}

// Check if user is authenticated and update navbar toggles (V5 RBAC)
function checkAuthStatus() {
    const token = getToken();
    const authContainer = document.getElementById("auth-container");
    const appContainer = document.getElementById("app-container");
    
    if (token) {
        authContainer.classList.add("hidden");
        appContainer.classList.remove("hidden");
        
        const userObj = JSON.parse(localStorage.getItem("current_user") || "{}");
        document.getElementById("user-fullname-display").innerText = `${userObj.fullname} (${userObj.role === 'admin' ? 'Admin' : 'User'})`;
        const initial = (userObj.fullname || userObj.username || "U").charAt(0).toUpperCase();
        document.getElementById("user-avatar-initial").innerText = initial;
        
        // V5 RBAC: Show/Hide User Management Navigation Tab
        const userTab = document.getElementById("tab-users");
        if (userObj.role === "admin") {
            userTab.classList.remove("hidden");
        } else {
            userTab.classList.add("hidden");
        }
        
        // Load initial app data
        switchTab("dashboard");
    } else {
        authContainer.classList.remove("hidden");
        appContainer.classList.add("hidden");
        toggleAuthCard("login");
    }
}

// Helper: Check if logged-in user is admin
function isCurrentUserAdmin() {
    const userObj = JSON.parse(localStorage.getItem("current_user") || "{}");
    return userObj.role === "admin";
}

// ----------------------------------------------------
// CONTRACTORS & MATERIAL DROPDOWN LISTS (LocalStorage)
// ----------------------------------------------------
const DEFAULT_CONTRACTORS = [
    "บริษัท มดงาน บุษยมาศ จำกัด",
    "บริษัท ปาริภัทร จำกัด",
    "ห้างหุ้นส่วนจำกัด สิทธิพรรณ คอนแท๊ก",
    "บริษัท สบายตา ดีเวลลอปเม้นท์ จำกัด",
    "ห้างหุ้นส่วนจำกัด อลงกรณ์การโยธา"
];

function getContractors() {
    let contractors = localStorage.getItem("contractors");
    if (!contractors) {
        contractors = JSON.stringify(DEFAULT_CONTRACTORS);
        localStorage.setItem("contractors", contractors);
    }
    return JSON.parse(contractors);
}

function saveContractor(name) {
    if (!name) return;
    const contractors = getContractors();
    if (!contractors.includes(name)) {
        contractors.push(name);
        localStorage.setItem("contractors", JSON.stringify(contractors));
    }
}

function populateContractorsDropdown(selectedVal = "") {
    const select = document.getElementById("form-contractor");
    if (!select) return;
    select.innerHTML = "";
    
    const promptOpt = document.createElement("option");
    promptOpt.value = "";
    promptOpt.innerText = "-- เลือกบริษัท/ห้างหุ้นส่วน --";
    select.appendChild(promptOpt);
    
    const contractors = getContractors();
    contractors.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c;
        opt.innerText = c;
        if (c === selectedVal) opt.selected = true;
        select.appendChild(opt);
    });
    
    const addOpt = document.createElement("option");
    addOpt.value = "ADD_NEW";
    addOpt.innerText = "+ เพิ่มบริษัทใหม่...";
    if (selectedVal === "ADD_NEW") addOpt.selected = true;
    select.appendChild(addOpt);
    
    toggleCustomContractorInput();
}

function toggleCustomContractorInput() {
    const select = document.getElementById("form-contractor");
    const container = document.getElementById("custom-contractor-container");
    if (select && select.value === "ADD_NEW") {
        container.classList.remove("hidden");
    } else if (container) {
        container.classList.add("hidden");
    }
}

function addNewContractorOption() {
    const input = document.getElementById("form-custom-contractor");
    const val = input.value.trim();
    if (val) {
        saveContractor(val);
        populateContractorsDropdown(val);
        input.value = "";
    } else {
        alert("กรุณาระบุชื่อบริษัท/ห้างหุ้นส่วน");
    }
}

// PO Contractor lists (V4)
const DEFAULT_PO_CONTRACTORS = [
    "บริษัท มดงาน บุษยมาศ จำกัด",
    "ห้างหุ้นส่วนจำกัด สิทธิพรรณ คอนแท๊ก"
];

function getPOContractors() {
    let contractors = localStorage.getItem("po_contractors");
    if (!contractors) {
        contractors = JSON.stringify(DEFAULT_PO_CONTRACTORS);
        localStorage.setItem("po_contractors", contractors);
    }
    return JSON.parse(contractors);
}

function savePOContractor(name) {
    if (!name) return;
    const contractors = getPOContractors();
    if (!contractors.includes(name)) {
        contractors.push(name);
        localStorage.setItem("po_contractors", JSON.stringify(contractors));
    }
}

function populatePOContractorsDropdown(selectedVal = "") {
    const select = document.getElementById("form-po-contractor");
    if (!select) return;
    select.innerHTML = "";
    
    const promptOpt = document.createElement("option");
    promptOpt.value = "";
    promptOpt.innerText = "-- เลือกผู้รับผิดชอบ PO --";
    select.appendChild(promptOpt);
    
    const contractors = getPOContractors();
    contractors.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c;
        opt.innerText = c;
        if (c === selectedVal) opt.selected = true;
        select.appendChild(opt);
    });
    
    const addOpt = document.createElement("option");
    addOpt.value = "ADD_NEW";
    addOpt.innerText = "+ เพิ่มบริษัทใหม่...";
    if (selectedVal === "ADD_NEW") addOpt.selected = true;
    select.appendChild(addOpt);
    
    toggleCustomPOContractorInput();
}

function toggleCustomPOContractorInput() {
    const select = document.getElementById("form-po-contractor");
    const container = document.getElementById("custom-po-contractor-container");
    if (select && select.value === "ADD_NEW") {
        container.classList.remove("hidden");
    } else if (container) {
        container.classList.add("hidden");
    }
}

function addNewPOContractorOption() {
    const input = document.getElementById("form-po-custom-contractor");
    const val = input.value.trim();
    if (val) {
        savePOContractor(val);
        populatePOContractorsDropdown(val);
        input.value = "";
    } else {
        alert("กรุณาระบุชื่อบริษัท/ห้างหุ้นส่วน");
    }
}

// Job Types list management (V3)
const DEFAULT_JOB_TYPES = [
    "งานเช่าเครื่องจักร",
    "งานคอนกรีต",
    "งานเหล็ก",
    "งานจ้างก่อสร้าง"
];

function getJobTypes() {
    let jobTypes = localStorage.getItem("job_types");
    if (!jobTypes) {
        jobTypes = JSON.stringify(DEFAULT_JOB_TYPES);
        localStorage.setItem("job_types", jobTypes);
    }
    return JSON.parse(jobTypes);
}

function saveJobType(name) {
    if (!name) return;
    const jobTypes = getJobTypes();
    if (!jobTypes.includes(name)) {
        jobTypes.push(name);
        localStorage.setItem("job_types", JSON.stringify(jobTypes));
    }
}

function populateJobTypesDropdown(selectedVal = "") {
    const select = document.getElementById("form-job-type");
    if (!select) return;
    select.innerHTML = "";
    
    const promptOpt = document.createElement("option");
    promptOpt.value = "";
    promptOpt.innerText = "-- เลือกประเภทงาน --";
    select.appendChild(promptOpt);
    
    const jobTypes = getJobTypes();
    jobTypes.forEach(jt => {
        const opt = document.createElement("option");
        opt.value = jt;
        opt.innerText = jt;
        if (jt === selectedVal) opt.selected = true;
        select.appendChild(opt);
    });
    
    const addOpt = document.createElement("option");
    addOpt.value = "ADD_NEW";
    addOpt.innerText = "+ เพิ่มประเภทงานใหม่...";
    if (selectedVal === "ADD_NEW") addOpt.selected = true;
    select.appendChild(addOpt);
    
    toggleCustomJobTypeInput();
}

function toggleCustomJobTypeInput() {
    const select = document.getElementById("form-job-type");
    const container = document.getElementById("custom-job-type-container");
    if (select && select.value === "ADD_NEW") {
        container.classList.remove("hidden");
    } else if (container) {
        container.classList.add("hidden");
    }
}

function addNewJobTypeOption() {
    const input = document.getElementById("form-custom-job-type");
    const val = input.value.trim();
    if (val) {
        saveJobType(val);
        populateJobTypesDropdown(val);
        input.value = "";
    } else {
        alert("กรุณาระบุชื่อประเภทงาน");
    }
}

// PO Materials list management (V4)
const DEFAULT_PO_MATERIALS = [
    "วัสดุงานก่อสร้าง",
    "วัสดุสำนักงาน"
];

function getPOMaterials() {
    let materials = localStorage.getItem("po_materials");
    if (!materials) {
        materials = JSON.stringify(DEFAULT_PO_MATERIALS);
        localStorage.setItem("po_materials", materials);
    }
    return JSON.parse(materials);
}

function savePOMaterial(name) {
    if (!name) return;
    const materials = getPOMaterials();
    if (!materials.includes(name)) {
        materials.push(name);
        localStorage.setItem("po_materials", JSON.stringify(materials));
    }
}

function populatePOMaterialsDropdown(selectedVal = "") {
    const select = document.getElementById("form-po-material-type");
    if (!select) return;
    select.innerHTML = "";
    
    const promptOpt = document.createElement("option");
    promptOpt.value = "";
    promptOpt.innerText = "-- เลือกประเภทวัสดุ --";
    select.appendChild(promptOpt);
    
    const materials = getPOMaterials();
    materials.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.innerText = m;
        if (m === selectedVal) opt.selected = true;
        select.appendChild(opt);
    });
    
    const addOpt = document.createElement("option");
    addOpt.value = "ADD_NEW";
    addOpt.innerText = "+ เพิ่มประเภทวัสดุใหม่...";
    if (selectedVal === "ADD_NEW") addOpt.selected = true;
    select.appendChild(addOpt);
    
    toggleCustomPOMaterialInput();
}

function toggleCustomPOMaterialInput() {
    const select = document.getElementById("form-po-material-type");
    const container = document.getElementById("custom-po-material-container");
    if (select && select.value === "ADD_NEW") {
        container.classList.remove("hidden");
    } else if (container) {
        container.classList.add("hidden");
    }
}

function addNewPOMaterialOption() {
    const input = document.getElementById("form-po-custom-material");
    const val = input.value.trim();
    if (val) {
        savePOMaterial(val);
        populatePOMaterialsDropdown(val);
        input.value = "";
    } else {
        alert("กรุณาระบุประเภทวัสดุ");
    }
}

// ----------------------------------------------------
// UI Toggles & Initialization
// ----------------------------------------------------
function toggleBankGuaranteeFields() {
    const paymentType = document.getElementById("form-guarantee-payment-type").value;
    const container = document.getElementById("bank-guarantee-fields-container");
    if (paymentType === "หนังสือค้ำประกันธนาคาร (LG)") {
        container.classList.remove("hidden");
    } else {
        container.classList.add("hidden");
        document.getElementById("form-guarantee-bank").value = "";
        document.getElementById("form-guarantee-expiry-date").value = "";
    }
}

function toggleRightAssignmentPercentageInput() {
    const rightAssignment = document.getElementById("form-right-assignment").value;
    const container = document.getElementById("right-assignment-percentage-container");
    if (rightAssignment === "โอนสิทธิ์") {
        container.classList.remove("hidden");
    } else {
        container.classList.add("hidden");
        document.getElementById("form-right-assignment-percentage").value = "";
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    const token = getToken();
    if (token) {
        showLoading("กำลังตรวจสอบเซสชันและปลุกเซิร์ฟเวอร์คลาวด์ กรุณารอประมาณ 1 นาที...");
        try {
            const response = await fetch("/api/auth/me", {
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (response.ok) {
                const user = await response.json();
                localStorage.setItem("current_user", JSON.stringify(user));
                checkAuthStatus();
            } else {
                handleLogout();
            }
        } catch (err) {
            console.error("Startup auth check error:", err);
            checkAuthStatus();
        } finally {
            hideLoading();
        }
    } else {
        checkAuthStatus();
    }
});

function initApp() {
    fetchDashboardStats();
    fetchDashboardAlerts();
    fetchDashboardPOAlerts();
    fetchProjects();
}

// ----------------------------------------------------
// TAB NAVIGATION
// ----------------------------------------------------
function switchTab(tabName) {
    const viewDashboard = document.getElementById("view-dashboard");
    const viewProjects = document.getElementById("view-projects");
    const viewPurchaseOrders = document.getElementById("view-purchase-orders");
    const viewUsers = document.getElementById("view-users");
    const viewAuditLogs = document.getElementById("view-audit-logs");
    
    const tabDashboardBtn = document.getElementById("tab-dashboard");
    const tabProjectsBtn = document.getElementById("tab-projects");
    const tabPOBtn = document.getElementById("tab-purchase-orders");
    const tabUsersBtn = document.getElementById("tab-users");
    const tabAuditLogsBtn = document.getElementById("tab-audit-logs");

    // Hide all views
    viewDashboard.classList.add("hidden");
    viewProjects.classList.add("hidden");
    viewPurchaseOrders.classList.add("hidden");
    viewUsers.classList.add("hidden");
    viewAuditLogs.classList.add("hidden");
    
    tabDashboardBtn.className = "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium";
    tabProjectsBtn.className = "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium";
    tabPOBtn.className = "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium";
    tabUsersBtn.className = "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium";
    tabAuditLogsBtn.className = "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium";

    if (tabName === "dashboard") {
        viewDashboard.classList.remove("hidden");
        tabDashboardBtn.className = "border-transparent text-indigo-600 hover:text-indigo-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-semibold tab-active";
        
        fetchDashboardStats();
        fetchDashboardAlerts();
        fetchDashboardPOAlerts();
    } else if (tabName === "projects") {
        viewProjects.classList.remove("hidden");
        tabProjectsBtn.className = "border-transparent text-indigo-600 hover:text-indigo-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-semibold tab-active";
        
        fetchProjects();
    } else if (tabName === "purchase-orders") {
        viewPurchaseOrders.classList.remove("hidden");
        tabPOBtn.className = "border-transparent text-indigo-600 hover:text-indigo-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-semibold tab-active";
        
        fetchPOs();
    } else if (tabName === "users") {
        viewUsers.classList.remove("hidden");
        tabUsersBtn.className = "border-transparent text-indigo-600 hover:text-indigo-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-semibold tab-active";
        
        fetchUsers();
    } else if (tabName === "audit-logs") {
        viewAuditLogs.classList.remove("hidden");
        tabAuditLogsBtn.className = "border-transparent text-indigo-600 hover:text-indigo-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-semibold tab-active";
        
        fetchAuditLogs();
    }
}

// ----------------------------------------------------
// DASHBOARD LOGIC
// ----------------------------------------------------
async function fetchDashboardStats() {
    try {
        const response = await secureFetch("/api/dashboard/stats");
        if (!response.ok) throw new Error("Failed to fetch stats");
        const stats = await response.json();
        
        document.getElementById("stat-total").innerText = stats.total_projects;
        document.getElementById("stat-active").innerText = stats.projects_by_status["กำลังดำเนินการ"] || 0;
        document.getElementById("stat-delayed").innerText = stats.projects_by_status["ล่าช้า"] || 0;
        document.getElementById("stat-delivered").innerText = stats.projects_by_status["ส่งมอบแล้ว"] || 0;
        document.getElementById("stat-active-budget").innerText = formatCurrency(stats.active_total_budget);
    } catch (error) {
        console.error("Error fetching stats:", error);
    }
}

async function fetchDashboardAlerts() {
    try {
        const response = await secureFetch("/api/dashboard/alerts");
        if (!response.ok) throw new Error("Failed to fetch alerts");
        const alerts = await response.json();
        
        const container = document.getElementById("alerts-container");
        const alertCountBadge = document.getElementById("alert-count");
        container.innerHTML = "";
        alertCountBadge.innerText = `${alerts.length} รายการ`;
        
        if (alerts.length === 0) {
            container.innerHTML = `
                <div class="bg-white rounded-xl p-6 border border-slate-150 text-center text-slate-400 text-sm">
                    <svg class="h-10 w-10 mx-auto text-slate-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    ไม่มีรายการส่งมอบ/วัสดุสัญญาหลักที่ต้องส่งมอบในอีก 14 วัน
                </div>
            `;
            return;
        }
        
        alerts.forEach(alert => {
            const isOverdue = alert.days_remaining < 0;
            const remainingText = isOverdue 
                ? `เกินกำหนดส่งมอบ ${Math.abs(alert.days_remaining)} วัน` 
                : alert.days_remaining === 0 
                    ? "ครบกำหนดส่งมอบวันนี้" 
                    : `เหลือเวลา ${alert.days_remaining} วัน`;
            
            const badgeClass = isOverdue ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-800";
            const borderClass = isOverdue ? "border-rose-500" : "border-amber-500";
            const iconBg = isOverdue ? "bg-rose-50 text-rose-600" : "bg-amber-50 text-amber-600";
            
            const alertEl = document.createElement("div");
            alertEl.className = `bg-white border-l-4 ${borderClass} rounded-xl p-4 shadow-sm flex items-center justify-between hover:shadow-md transition duration-150 cursor-pointer`;
            alertEl.onclick = () => {
                switchTab('projects');
                openDetailModal(alert.project_id);
            };
            alertEl.innerHTML = `
                <div class="flex items-start space-x-3">
                    <div class="mt-0.5 p-1 ${iconBg} rounded-lg">
                        <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    </div>
                    <div>
                        <p class="font-semibold text-slate-900 text-sm">${alert.deliverable_name}</p>
                        <p class="text-xs text-slate-500 mt-1">โครงการ: ${alert.project_name}</p>
                    </div>
                </div>
                <div class="text-right whitespace-nowrap pl-4">
                    <span class="${badgeClass} text-[10px] sm:text-xs px-2.5 py-0.5 rounded-full font-bold">${remainingText}</span>
                    <p class="text-xs text-slate-400 mt-1.5">กำหนดส่งมอบ: ${formatThaiDate(alert.due_date)}</p>
                </div>
            `;
            container.appendChild(alertEl);
        });
    } catch (error) {
        console.error("Error fetching alerts:", error);
    }
}

async function fetchDashboardPOAlerts() {
    try {
        const response = await secureFetch("/api/dashboard/po-alerts");
        if (!response.ok) throw new Error("Failed to fetch PO alerts");
        const alerts = await response.json();
        
        const container = document.getElementById("po-alerts-container");
        const alertCountBadge = document.getElementById("po-alert-count");
        container.innerHTML = "";
        alertCountBadge.innerText = `${alerts.length} รายการ`;
        
        if (alerts.length === 0) {
            container.innerHTML = `
                <div class="bg-white rounded-xl p-6 border border-slate-150 text-center text-slate-400 text-sm">
                    <svg class="h-10 w-10 mx-auto text-slate-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    ไม่มีแจ้งเตือนการส่งมอบใบสั่งซื้อ (PO) ในระยะนี้
                </div>
            `;
            return;
        }
        
        alerts.forEach(alert => {
            const isOverdue = alert.days_remaining < 0;
            const remainingText = isOverdue 
                ? `เกินกำหนดส่ง PO ${Math.abs(alert.days_remaining)} วัน` 
                : alert.days_remaining === 0 
                    ? "ครบกำหนดส่ง PO วันนี้" 
                    : `เหลือเวลาส่ง PO ${alert.days_remaining} วัน`;
            
            const badgeClass = isOverdue ? "bg-rose-100 text-rose-800" : "bg-orange-100 text-orange-800";
            const borderClass = isOverdue ? "border-rose-500" : "border-orange-500";
            const iconBg = isOverdue ? "bg-rose-50 text-rose-600" : "bg-orange-50 text-orange-600";
            
            const alertEl = document.createElement("div");
            alertEl.className = `bg-white border-l-4 ${borderClass} rounded-xl p-4 shadow-sm flex items-center justify-between hover:shadow-md transition duration-150 cursor-pointer`;
            alertEl.onclick = () => {
                switchTab('purchase-orders');
                openPODetailModal(alert.po_id);
            };
            alertEl.innerHTML = `
                <div class="flex items-start space-x-3">
                    <div class="mt-0.5 p-1 ${iconBg} rounded-lg">
                        <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                    </div>
                    <div>
                        <p class="font-semibold text-slate-900 text-sm">เลขที่ PO: ${alert.po_number}</p>
                        <p class="text-xs text-slate-500 mt-1">โครงการ: ${alert.project_name}</p>
                        <p class="text-xs text-slate-400 mt-0.5">งบประมาณ PO: ${formatCurrency(alert.budget)}</p>
                    </div>
                </div>
                <div class="text-right whitespace-nowrap pl-4">
                    <span class="${badgeClass} text-[10px] sm:text-xs px-2.5 py-0.5 rounded-full font-bold">${remainingText}</span>
                    <p class="text-xs text-slate-400 mt-1.5">กำหนดส่งมอบ: ${formatThaiDate(alert.due_date)}</p>
                </div>
            `;
            container.appendChild(alertEl);
        });
    } catch (error) {
        console.error("Error fetching PO alerts:", error);
    }
}

// ----------------------------------------------------
// PROJECTS LOGIC
// ----------------------------------------------------
async function fetchProjects() {
    try {
        const response = await secureFetch("/api/projects");
        if (!response.ok) throw new Error("Failed to fetch projects");
        projectsCache = await response.json();
        renderProjectsTable(projectsCache);
    } catch (error) {
        console.error("Error fetching projects:", error);
    }
}

function renderProjectsTable(projects) {
    const tableBody = document.getElementById("projects-table-body");
    const noProjectsMsg = document.getElementById("no-projects-message");
    tableBody.innerHTML = "";
    
    if (projects.length === 0) {
        noProjectsMsg.classList.remove("hidden");
        return;
    }
    noProjectsMsg.classList.add("hidden");
    
    const isAdmin = isCurrentUserAdmin();
    
    projects.forEach(project => {
        let badgeColor = "bg-blue-100 text-blue-800";
        if (project.status === "ล่าช้า") {
            badgeColor = "bg-rose-100 text-rose-800";
        } else if (project.status === "ส่งมอบแล้ว") {
            badgeColor = "bg-emerald-100 text-emerald-800";
        }
        
        // V5 RBAC: Show delete button for admins only
        const deleteButton = isAdmin 
            ? `<button onclick="deleteProject(${project.id})" class="text-rose-600 hover:text-rose-900 bg-rose-50 hover:bg-rose-100 px-2.5 py-1.5 rounded-lg transition duration-150">ลบ</button>` 
            : "";
        
        const row = document.createElement("tr");
        row.className = "hover:bg-slate-50/50 transition duration-150";
        row.innerHTML = `
            <td class="px-6 py-4 font-semibold text-slate-500 text-xs">${project.id}</td>
            <td class="px-6 py-4 font-semibold text-slate-900 text-sm hover:text-indigo-600 cursor-pointer" onclick="openDetailModal(${project.id})">${project.name}</td>
            <td class="px-6 py-4 text-slate-500 text-sm">${project.owner}</td>
            <td class="px-6 py-4 text-slate-700 text-sm font-medium">${project.contractor || "-"}</td>
            <td class="px-6 py-4 text-slate-600 text-sm">${project.job_type || "-"}</td>
            <td class="px-6 py-4 font-semibold text-slate-900 text-sm">${formatCurrency(project.budget)}</td>
            <td class="px-6 py-4 text-slate-500 text-xs">${(project.start_date || project.end_date) ? `${formatThaiDate(project.start_date)} - ${formatThaiDate(project.end_date)}` : "-"}</td>
            <td class="px-6 py-4">
                <span class="${badgeColor} text-xs px-2.5 py-0.5 rounded-full font-bold">${project.status}</span>
            </td>
            <td class="px-6 py-4 text-center whitespace-nowrap text-xs font-medium space-x-2">
                <button onclick="openDetailModal(${project.id})" class="text-indigo-600 hover:text-indigo-900 bg-indigo-50 hover:bg-indigo-100 px-2.5 py-1.5 rounded-lg transition duration-150">ดูรายละเอียด</button>
                <button onclick="editProject(${project.id})" class="text-amber-600 hover:text-amber-900 bg-amber-50 hover:bg-amber-100 px-2.5 py-1.5 rounded-lg transition duration-150">แก้ไข</button>
                ${deleteButton}
            </td>
        `;
        tableBody.appendChild(row);
    });
}

function filterProjects() {
    const searchQuery = document.getElementById("search-input").value.toLowerCase();
    const statusFilter = document.getElementById("status-filter").value;
    
    const filtered = projectsCache.filter(project => {
        const matchesSearch = project.name.toLowerCase().includes(searchQuery) ||
                             project.owner.toLowerCase().includes(searchQuery) ||
                             (project.contractor && project.contractor.toLowerCase().includes(searchQuery)) ||
                             (project.job_type && project.job_type.toLowerCase().includes(searchQuery)) ||
                             project.status.toLowerCase().includes(searchQuery);
                             
        const matchesStatus = statusFilter === "ทั้งหมด" || project.status === statusFilter;
        
        return matchesSearch && matchesStatus;
    });
    
    renderProjectsTable(filtered);
}

// ----------------------------------------------------
// PROJECT FORM MODAL (ADD / EDIT)
// ----------------------------------------------------
function openProjectModal(title = "เพิ่มโครงการสัญญาใหม่") {
    document.getElementById("modal-title").innerText = title;
    document.getElementById("project-form").reset();
    document.getElementById("form-project-id").value = "";
    document.getElementById("upload-section").classList.remove("hidden");
    
    populateContractorsDropdown();
    document.getElementById("form-custom-contractor").value = "";
    
    populateJobTypesDropdown();
    document.getElementById("form-custom-job-type").value = "";
    
    document.getElementById("form-contract-signing-date").value = "";
    document.getElementById("form-work-order-date").value = "";
    document.getElementById("form-right-assignment").value = "ไม่ได้โอนสิทธิ์";
    document.getElementById("form-right-assignment-percentage").value = "";
    document.getElementById("form-guarantee-bank").value = "";
    document.getElementById("form-guarantee-expiry-date").value = "";
    document.getElementById("form-guarantee-receipt-number").value = "";
    
    toggleBankGuaranteeFields();
    toggleRightAssignmentPercentageInput();
    
    document.getElementById("project-modal").classList.remove("hidden");
}

function closeProjectModal() {
    document.getElementById("project-modal").classList.add("hidden");
}

async function saveProject(event) {
    event.preventDefault();
    
    const projectId = document.getElementById("form-project-id").value;
    
    const counterpartDate = document.getElementById("form-counterpart-date").value || null;
    const guaranteeReceiptDate = document.getElementById("form-guarantee-receipt-date").value || null;
    const workOrderDate = document.getElementById("form-work-order-date").value || null;
    const contractSigningDate = document.getElementById("form-contract-signing-date").value || null;
    const guaranteeReceiptNumber = document.getElementById("form-guarantee-receipt-number").value || null;
    const startDate = document.getElementById("form-start-date").value || null;
    const endDate = document.getElementById("form-end-date").value || null;
    
    let contractorVal = document.getElementById("form-contractor").value;
    if (contractorVal === "ADD_NEW") {
        const customName = document.getElementById("form-custom-contractor").value.trim();
        if (customName) {
            saveContractor(customName);
            contractorVal = customName;
        } else {
            alert("กรุณาระบุชื่อบริษัท/ห้างหุ้นส่วนผู้รับผิดชอบ");
            return;
        }
    }
    
    let jobTypeVal = document.getElementById("form-job-type").value;
    if (jobTypeVal === "ADD_NEW") {
        const customJob = document.getElementById("form-custom-job-type").value.trim();
        if (customJob) {
            saveJobType(customJob);
            jobTypeVal = customJob;
        } else {
            alert("กรุณาระบุชื่อประเภทงาน");
            return;
        }
    }
    
    const rightAssignmentVal = document.getElementById("form-right-assignment").value;
    let rightPercent = null;
    if (rightAssignmentVal === "โอนสิทธิ์") {
        const pctInput = document.getElementById("form-right-assignment-percentage").value;
        rightPercent = pctInput ? parseFloat(pctInput) : 0.0;
    }
    
    const paymentTypeVal = document.getElementById("form-guarantee-payment-type").value;
    let bankVal = null;
    let expiryVal = null;
    if (paymentTypeVal === "หนังสือค้ำประกันธนาคาร (LG)") {
        bankVal = document.getElementById("form-guarantee-bank").value || null;
        expiryVal = document.getElementById("form-guarantee-expiry-date").value || null;
    }
    
    const projectData = {
        name: document.getElementById("form-name").value,
        owner: document.getElementById("form-owner").value,
        budget: parseFloat(document.getElementById("form-budget").value),
        status: document.getElementById("form-status").value,
        start_date: startDate,
        end_date: endDate,
        contract_signing_date: contractSigningDate,
        
        contract_number: document.getElementById("form-contract-number").value || null,
        contractor: contractorVal || null,
        counterpart_status: document.getElementById("form-counterpart-status").value,
        counterpart_date: counterpartDate,
        guarantee_amount: parseFloat(document.getElementById("form-guarantee-amount").value) || 0.0,
        guarantee_payment_type: paymentTypeVal,
        guarantee_receipt_status: document.getElementById("form-guarantee-receipt-status").value,
        guarantee_receipt_date: guaranteeReceiptDate,
        guarantee_receipt_number: guaranteeReceiptNumber,
        
        work_order_date: workOrderDate,
        guarantee_bank: bankVal,
        guarantee_expiry_date: expiryVal,
        job_type: jobTypeVal || null,
        right_assignment: rightAssignmentVal,
        right_assignment_percentage: rightPercent
    };
    
    try {
        showLoading("กำลังบันทึกข้อมูลโครงการ...");
        let response;
        let savedProject;
        
        if (projectId) {
            response = await secureFetch(`/api/projects/${projectId}`, {
                method: "PUT",
                body: JSON.stringify(projectData)
            });
            if (!response.ok) throw new Error("Failed to update project");
            savedProject = await response.json();
        } else {
            response = await secureFetch("/api/projects", {
                method: "POST",
                body: JSON.stringify(projectData)
            });
            if (!response.ok) throw new Error("Failed to create project");
            savedProject = await response.json();
            
            const fileInput = document.getElementById("form-file");
            if (fileInput.files.length > 0) {
                const formData = new FormData();
                formData.append("file", fileInput.files[0]);
                
                const uploadResponse = await secureFetch(`/api/projects/${savedProject.id}/documents`, {
                    method: "POST",
                    body: formData
                });
                if (!uploadResponse.ok) console.error("Failed to upload project document during creation");
            }
        }
        
        const receiptInput = document.getElementById("form-guarantee-receipt-file");
        if (receiptInput.files.length > 0) {
            const formData = new FormData();
            formData.append("file", receiptInput.files[0]);
            
            const uploadResponse = await secureFetch(`/api/projects/${savedProject.id}/guarantee-receipt`, {
                method: "POST",
                body: formData
            });
            if (!uploadResponse.ok) {
                const errData = await uploadResponse.json();
                throw new Error(errData.detail || "Failed to upload guarantee receipt file");
            }
        }

        const guarDocInput = document.getElementById("form-guarantee-document-file");
        if (guarDocInput && guarDocInput.files.length > 0) {
            const formData = new FormData();
            formData.append("file", guarDocInput.files[0]);
            
            const uploadResponse = await secureFetch(`/api/projects/${savedProject.id}/guarantee-document`, {
                method: "POST",
                body: formData
            });
            if (!uploadResponse.ok) {
                const errData = await uploadResponse.json();
                throw new Error(errData.detail || "Failed to upload guarantee document file");
            }
        }
        
        closeProjectModal();
        initApp(); 
    } catch (error) {
        console.error("Error saving project:", error);
        alert("เกิดข้อผิดพลาดในการบันทึกโครงการ: " + error.message);
    } finally {
        hideLoading();
    }
}

function editProject(id) {
    const project = projectsCache.find(p => p.id === id);
    if (!project) return;
    
    openProjectModal("แก้ไขโครงการสัญญา");
    document.getElementById("form-project-id").value = project.id;
    document.getElementById("form-name").value = project.name;
    document.getElementById("form-owner").value = project.owner;
    document.getElementById("form-budget").value = project.budget;
    document.getElementById("form-status").value = project.status;
    document.getElementById("form-start-date").value = project.start_date || "";
    document.getElementById("form-end-date").value = project.end_date || "";
    document.getElementById("form-contract-signing-date").value = project.contract_signing_date || "";
    
    document.getElementById("form-contract-number").value = project.contract_number || "";
    document.getElementById("form-counterpart-status").value = project.counterpart_status || "ยังไม่ได้รับ";
    document.getElementById("form-counterpart-date").value = project.counterpart_date || "";
    document.getElementById("form-guarantee-amount").value = project.guarantee_amount || 0;
    document.getElementById("form-guarantee-payment-type").value = project.guarantee_payment_type || "หนังสือค้ำประกันธนาคาร (LG)";
    document.getElementById("form-guarantee-receipt-status").value = project.guarantee_receipt_status || "ยังไม่ได้รับ";
    document.getElementById("form-guarantee-receipt-date").value = project.guarantee_receipt_date || "";
    document.getElementById("form-guarantee-receipt-number").value = project.guarantee_receipt_number || "";
    
    document.getElementById("form-work-order-date").value = project.work_order_date || "";
    document.getElementById("form-right-assignment").value = project.right_assignment || "ไม่ได้โอนสิทธิ์";
    document.getElementById("form-right-assignment-percentage").value = project.right_assignment_percentage !== null ? project.right_assignment_percentage : "";
    document.getElementById("form-guarantee-bank").value = project.guarantee_bank || "";
    document.getElementById("form-guarantee-expiry-date").value = project.guarantee_expiry_date || "";
    
    toggleBankGuaranteeFields();
    toggleRightAssignmentPercentageInput();
    
    if (project.contractor) {
        saveContractor(project.contractor);
        populateContractorsDropdown(project.contractor);
    } else {
        populateContractorsDropdown();
    }
    
    if (project.job_type) {
        saveJobType(project.job_type);
        populateJobTypesDropdown(project.job_type);
    } else {
        populateJobTypesDropdown();
    }
    
    document.getElementById("upload-section").classList.add("hidden");
}

async function deleteProject(id) {
    if (!confirm("คุณต้องการลบโครงการนี้ใช่หรือไม่? การดำเนินการนี้จะลบรายการส่งมอบและเอกสารแนบทั้งหมด")) return;
    
    try {
        showLoading("กำลังลบข้อมูลโครงการ...");
        const response = await secureFetch(`/api/projects/${id}`, {
            method: "DELETE"
        });
        if (response.status === 403) {
            const err = await response.json();
            alert(err.detail || "สิทธิ์การใช้งานไม่เพียงพอสำหรับการลบโครงการ");
            return;
        }
        if (!response.ok) throw new Error("Failed to delete project");
        initApp();
    } catch (error) {
        console.error("Error deleting project:", error);
        alert("ไม่สามารถลบโครงการได้: " + error.message);
    } finally {
        hideLoading();
    }
}

// ----------------------------------------------------
// PROJECT DETAILS MODAL & SUB-COMPONENTS
// ----------------------------------------------------
async function openDetailModal(id) {
    currentProjectId = id;
    
    try {
        const response = await secureFetch(`/api/projects/${id}`);
        if (!response.ok) throw new Error("Failed to fetch project details");
        const project = await response.json();
        
        currentProjectRightAssignment = project.right_assignment || "ไม่ได้โอนสิทธิ์";
        
        document.getElementById("detail-project-name").innerText = project.name;
        document.getElementById("detail-project-owner").innerText = `เจ้าของโครงการ: ${project.owner}`;
        
        const statusBadge = document.getElementById("detail-project-status");
        statusBadge.innerText = project.status;
        let badgeColor = "bg-blue-100 text-blue-800";
        if (project.status === "ล่าช้า") badgeColor = "bg-rose-100 text-rose-800";
        if (project.status === "ส่งมอบแล้ว") badgeColor = "bg-emerald-100 text-emerald-800";
        statusBadge.className = `px-2.5 py-0.5 rounded-full text-xs font-bold ${badgeColor}`;
        
        document.getElementById("detail-contract-number").innerText = project.contract_number || "-";
        document.getElementById("detail-contractor").innerText = project.contractor || "-";
        document.getElementById("detail-job-type").innerText = project.job_type || "-";
        document.getElementById("detail-budget").innerText = formatCurrency(project.budget);
        document.getElementById("detail-contract-signing-date").innerText = formatThaiDate(project.contract_signing_date);
        document.getElementById("detail-start-date").innerText = formatThaiDate(project.start_date);
        document.getElementById("detail-end-date").innerText = formatThaiDate(project.end_date);
        document.getElementById("detail-work-order-date").innerText = formatThaiDate(project.work_order_date);
        
        let counterpartText = project.counterpart_status;
        if (project.counterpart_status === "ได้รับแล้ว" && project.counterpart_date) {
            counterpartText += ` (${formatThaiDate(project.counterpart_date)})`;
        }
        document.getElementById("detail-counterpart-status").innerText = counterpartText;
        
        let assignmentText = project.right_assignment || "ไม่ได้โอนสิทธิ์";
        if (project.right_assignment === "โอนสิทธิ์" && project.right_assignment_percentage !== null) {
            assignmentText += ` (${project.right_assignment_percentage}%)`;
        }
        document.getElementById("detail-right-assignment").innerText = assignmentText;
        
        document.getElementById("detail-guarantee-amount").innerText = formatCurrency(project.guarantee_amount);
        document.getElementById("detail-guarantee-payment-type").innerText = project.guarantee_payment_type;
        
        const lgBankLabel = document.getElementById("detail-guarantee-bank-label");
        const lgBankField = document.getElementById("detail-guarantee-bank");
        const lgExpLabel = document.getElementById("detail-guarantee-expiry-label");
        const lgExpField = document.getElementById("detail-guarantee-expiry-date");
        
        if (project.guarantee_payment_type === "หนังสือค้ำประกันธนาคาร (LG)") {
            lgBankLabel.classList.remove("hidden");
            lgBankField.classList.remove("hidden");
            lgExpLabel.classList.remove("hidden");
            lgExpField.classList.remove("hidden");
            lgBankField.innerText = project.guarantee_bank || "-";
            lgExpField.innerText = formatThaiDate(project.guarantee_expiry_date);
        } else {
            lgBankLabel.classList.add("hidden");
            lgBankField.classList.add("hidden");
            lgExpLabel.classList.add("hidden");
            lgExpField.classList.add("hidden");
        }
        
        let receiptText = project.guarantee_receipt_status;
        if (project.guarantee_receipt_status === "ได้รับแล้ว" && project.guarantee_receipt_date) {
            receiptText += ` (${formatThaiDate(project.guarantee_receipt_date)})`;
        }
        document.getElementById("detail-guarantee-receipt-status").innerText = receiptText;
        document.getElementById("detail-guarantee-receipt-number").innerText = project.guarantee_receipt_number || "-";
        
        // V5 Project Audit Trail bindings
        document.getElementById("detail-project-created-by").innerText = project.created_by || "system";
        document.getElementById("detail-project-created-at").innerText = formatTimestamp(project.created_at);
        document.getElementById("detail-project-updated-by").innerText = project.updated_by || "system";
        document.getElementById("detail-project-updated-at").innerText = formatTimestamp(project.updated_at);
        
        renderGuaranteeDocumentFile(project);
        renderGuaranteeReceiptFile(project);
        renderDocumentsList(project.documents);
        setupDeliverablesDynamicFormAndHeader(project);
        renderDeliverablesTable(project.deliverables);
        
        document.getElementById("detail-modal").classList.remove("hidden");
    } catch (error) {
        console.error("Error loading project details:", error);
        alert("ไม่สามารถโหลดรายละเอียดโครงการได้: " + error.message);
    }
}

function closeDetailModal() {
    document.getElementById("detail-modal").classList.add("hidden");
    currentProjectId = null;
    initApp(); 
}

// ----------------------------------------------------
// GUARANTEE RECEIPTS SUB-LOGIC (V2)
// ----------------------------------------------------
function renderGuaranteeReceiptFile(project) {
    const fileContainer = document.getElementById("detail-guarantee-receipt-file-container");
    const uploadContainer = document.getElementById("detail-guarantee-receipt-upload-container");
    
    fileContainer.innerHTML = "";
    document.getElementById("detail-guarantee-receipt-input").value = "";
    
    const isAdmin = isCurrentUserAdmin();
    
    if (project.guarantee_receipt_path) {
        uploadContainer.classList.add("hidden");
        
        // V5 RBAC: Show file delete only for Admin
        const deleteButton = isAdmin 
            ? `
            <button onclick="deleteGuaranteeReceipt(${project.id})" class="text-rose-500 hover:text-rose-700 p-1 rounded hover:bg-rose-50 transition duration-150" title="ลบใบเสร็จ">
                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
            ` 
            : "";
        
        fileContainer.innerHTML = `
            <div class="flex items-center space-x-2 min-w-0 flex-1">
                <svg class="h-4 w-4 text-emerald-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="font-medium text-slate-700 truncate" title="${project.guarantee_receipt_filename}">${project.guarantee_receipt_filename}</span>
            </div>
            <div class="flex items-center space-x-1.5 ml-3">
                <a href="${project.guarantee_receipt_path}" target="_blank" download class="text-slate-500 hover:text-slate-700 p-1 rounded hover:bg-slate-100 transition duration-150" title="ดาวน์โหลดใบเสร็จ">
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                </a>
                ${deleteButton}
            </div>
        `;
    } else {
        uploadContainer.classList.remove("hidden");
        fileContainer.innerHTML = `
            <span class="text-slate-400 italic">ยังไม่ได้อัปโหลดหลักฐานใบเสร็จ</span>
        `;
    }
}

async function uploadGuaranteeReceipt() {
    const fileInput = document.getElementById("detail-guarantee-receipt-input");
    if (fileInput.files.length === 0) {
        alert("กรุณาเลือกไฟล์ก่อนอัปโหลด");
        return;
    }
    
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    
    try {
        const response = await secureFetch(`/api/projects/${currentProjectId}/guarantee-receipt`, {
            method: "POST",
            body: formData
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to upload file");
        }
        
        openDetailModal(currentProjectId);
    } catch (error) {
        console.error("Error uploading receipt:", error);
        alert("เกิดข้อผิดพลาดในการอัปโหลดไฟล์: " + error.message);
    }
}

async function deleteGuaranteeReceipt(id) {
    if (!confirm("คุณแน่ใจว่าต้องการลบไฟล์ใบเสร็จเงินค้ำประกันสัญญานี้?")) return;
    
    try {
        const response = await secureFetch(`/api/projects/${id}/guarantee-receipt`, {
            method: "DELETE"
        });
        if (response.status === 403) {
            const err = await response.json();
            alert(err.detail || "สิทธิ์ไม่เพียงพอสำหรับการลบใบเสร็จค้ำประกัน");
            return;
        }
        if (!response.ok) throw new Error("Failed to delete receipt");
        openDetailModal(currentProjectId);
    } catch (error) {
        console.error("Error deleting receipt:", error);
        alert("เกิดข้อผิดพลาดในการลบไฟล์: " + error.message);
    }
}

function renderGuaranteeDocumentFile(project) {
    const fileContainer = document.getElementById("detail-guarantee-document-file-container");
    const uploadContainer = document.getElementById("detail-guarantee-document-upload-container");
    
    fileContainer.innerHTML = "";
    document.getElementById("detail-guarantee-document-input").value = "";
    
    const isAdmin = isCurrentUserAdmin();
    
    if (project.guarantee_document_path) {
        uploadContainer.classList.add("hidden");
        
        const deleteButton = isAdmin 
            ? `
            <button onclick="deleteGuaranteeDocument(${project.id})" class="text-rose-500 hover:text-rose-700 p-1 rounded hover:bg-rose-50 transition duration-150" title="ลบหลักฐานค้ำประกัน">
                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
            ` 
            : "";
        
        fileContainer.innerHTML = `
            <div class="flex items-center space-x-2 min-w-0 flex-1">
                <svg class="h-4 w-4 text-emerald-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="font-medium text-slate-700 truncate" title="${project.guarantee_document_filename}">${project.guarantee_document_filename}</span>
            </div>
            <div class="flex items-center space-x-1.5 ml-3">
                <a href="${project.guarantee_document_path}" target="_blank" download class="text-slate-500 hover:text-slate-700 p-1 rounded hover:bg-slate-100 transition duration-150" title="ดาวน์โหลดหลักฐาน">
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                </a>
                ${deleteButton}
            </div>
        `;
    } else {
        uploadContainer.classList.remove("hidden");
        fileContainer.innerHTML = `
            <span class="text-slate-400 italic">ยังไม่ได้อัปโหลดหลักฐานการค้ำประกัน</span>
        `;
    }
}

async function uploadGuaranteeDocument() {
    const fileInput = document.getElementById("detail-guarantee-document-input");
    if (fileInput.files.length === 0) {
        alert("กรุณาเลือกไฟล์ก่อนอัปโหลด");
        return;
    }
    
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    
    try {
        showLoading("กำลังอัปโหลดไฟล์หลักฐานการค้ำประกัน...");
        const response = await secureFetch(`/api/projects/${currentProjectId}/guarantee-document`, {
            method: "POST",
            body: formData
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to upload file");
        }
        
        openDetailModal(currentProjectId);
    } catch (error) {
        console.error("Error uploading document:", error);
        alert("เกิดข้อผิดพลาดในการอัปโหลดไฟล์: " + error.message);
    } finally {
        hideLoading();
    }
}

async function deleteGuaranteeDocument(id) {
    if (!confirm("คุณแน่ใจว่าต้องการลบไฟล์หลักฐานการค้ำประกันนี้?")) return;
    
    try {
        showLoading("กำลังลบไฟล์หลักฐานการค้ำประกัน...");
        const response = await secureFetch(`/api/projects/${id}/guarantee-document`, {
            method: "DELETE"
        });
        if (response.status === 403) {
            const err = await response.json();
            alert(err.detail || "สิทธิ์ไม่เพียงพอสำหรับการลบหลักฐานการค้ำประกัน");
            return;
        }
        if (!response.ok) throw new Error("Failed to delete document");
        openDetailModal(currentProjectId);
    } catch (error) {
        console.error("Error deleting document:", error);
        alert("เกิดข้อผิดพลาดในการลบไฟล์: " + error.message);
    } finally {
        hideLoading();
    }
}

// ----------------------------------------------------
// DELIVERABLES SUB-LOGIC
// ----------------------------------------------------
function setupDeliverablesDynamicFormAndHeader(project) {
    const headerRow = document.getElementById("detail-deliverables-header-row");
    const invoiceContainer = document.getElementById("add-deliv-invoice-container");
    
    if (project.right_assignment === "โอนสิทธิ์") {
        headerRow.innerHTML = `
            <th scope="col" class="px-4 py-3">รายการส่งมอบ / วัสดุ</th>
            <th scope="col" class="px-4 py-3">เลขที่การส่งภายใน (Internal)</th>
            <th scope="col" class="px-4 py-3">เลขที่การส่งภายนอก (External)</th>
            <th scope="col" class="px-4 py-3">วันที่ต้องส่งมอบ</th>
            <th scope="col" class="px-4 py-3">สถานะ</th>
            <th scope="col" class="px-4 py-3 text-center">จัดการ</th>
        `;
        
        invoiceContainer.innerHTML = `
            <div>
                <input type="text" id="add-deliv-internal-no" placeholder="เลขที่การส่งภายใน (Internal No.)..." class="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500">
            </div>
            <div>
                <input type="text" id="add-deliv-external-no" placeholder="เลขที่การส่งภายนอก (External No.)..." class="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500">
            </div>
        `;
    } else {
        headerRow.innerHTML = `
            <th scope="col" class="px-4 py-3">รายการส่งมอบ / วัสดุ</th>
            <th scope="col" class="px-4 py-3">เลขที่ใบส่งของ</th>
            <th scope="col" class="px-4 py-3">วันที่ต้องส่งมอบ</th>
            <th scope="col" class="px-4 py-3">สถานะ</th>
            <th scope="col" class="px-4 py-3 text-center">จัดการ</th>
        `;
        
        invoiceContainer.innerHTML = `
            <div class="md:col-span-2">
                <input type="text" id="add-deliv-delivery-no" placeholder="เลขที่ใบส่งของ (Delivery Invoice No.)..." class="w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500">
            </div>
        `;
    }
}

function renderDeliverablesTable(deliverables) {
    const body = document.getElementById("detail-deliverables-body");
    const countBadge = document.getElementById("detail-deliv-count");
    const noDelivMsg = document.getElementById("no-deliverables-message");
    
    body.innerHTML = "";
    countBadge.innerText = `${deliverables.length} รายการ`;
    
    if (deliverables.length === 0) {
        noDelivMsg.classList.remove("hidden");
        return;
    }
    noDelivMsg.classList.add("hidden");
    
    deliverables.sort((a,b) => new Date(a.due_date) - new Date(b.due_date));
    
    const isAdmin = isCurrentUserAdmin();
    
    deliverables.forEach(del => {
        const isDone = del.status === "ส่งมอบแล้ว";
        const badgeColor = isDone ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800";
        
        // V5 RBAC: Show deliverable delete button only for admins
        const deleteButton = isAdmin 
            ? `
            <button onclick="deleteDeliverable(${del.id})" class="text-rose-600 hover:text-rose-800 hover:bg-rose-50 p-1.5 rounded transition duration-150" title="ลบงวดงาน">
                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
            ` 
            : "";
        
        const row = document.createElement("tr");
        row.className = "hover:bg-slate-50 transition duration-150";
        
        if (currentProjectRightAssignment === "โอนสิทธิ์") {
            row.innerHTML = `
                <td class="px-4 py-3 font-semibold text-slate-800">${del.name}</td>
                <td class="px-4 py-3 text-slate-600 font-mono">${del.internal_delivery_no || "-"}</td>
                <td class="px-4 py-3 text-slate-600 font-mono">${del.external_delivery_no || "-"}</td>
                <td class="px-4 py-3 text-slate-500">${formatThaiDate(del.due_date)}</td>
                <td class="px-4 py-3">
                    <span class="${badgeColor} px-2 py-0.5 rounded font-bold">${del.status}</span>
                </td>
                <td class="px-4 py-3 text-center whitespace-nowrap space-x-1.5">
                    <button onclick="toggleDeliverableStatus(${del.id}, '${del.status}')" class="text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-2 py-1 rounded transition duration-150">
                        ${isDone ? "ทำเป็นรอดำเนินการ" : "ทำเป็นส่งมอบแล้ว"}
                    </button>
                    ${deleteButton}
                </td>
            `;
        } else {
            row.innerHTML = `
                <td class="px-4 py-3 font-semibold text-slate-800">${del.name}</td>
                <td class="px-4 py-3 text-slate-600 font-mono">${del.delivery_no || "-"}</td>
                <td class="px-4 py-3 text-slate-500">${formatThaiDate(del.due_date)}</td>
                <td class="px-4 py-3">
                    <span class="${badgeColor} px-2 py-0.5 rounded font-bold">${del.status}</span>
                </td>
                <td class="px-4 py-3 text-center whitespace-nowrap space-x-1.5">
                    <button onclick="toggleDeliverableStatus(${del.id}, '${del.status}')" class="text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-2 py-1 rounded transition duration-150">
                        ${isDone ? "ทำเป็นรอดำเนินการ" : "ทำเป็นส่งมอบแล้ว"}
                    </button>
                    ${deleteButton}
                </td>
            `;
        }
        body.appendChild(row);
    });
}

async function addDeliverable(event) {
    event.preventDefault();
    
    const name = document.getElementById("add-deliv-name").value;
    const due_date = document.getElementById("add-deliv-due").value;
    
    let deliveryNoVal = null;
    let internalNoVal = null;
    let externalNoVal = null;
    
    if (currentProjectRightAssignment === "โอนสิทธิ์") {
        internalNoVal = document.getElementById("add-deliv-internal-no").value || null;
        externalNoVal = document.getElementById("add-deliv-external-no").value || null;
    } else {
        deliveryNoVal = document.getElementById("add-deliv-delivery-no").value || null;
    }
    
    const deliverableData = {
        name,
        due_date,
        status: "รอดำเนินการ",
        delivery_no: deliveryNoVal,
        internal_delivery_no: internalNoVal,
        external_delivery_no: externalNoVal
    };
    
    try {
        const response = await secureFetch(`/api/projects/${currentProjectId}/deliverables`, {
            method: "POST",
            body: JSON.stringify(deliverableData)
        });
        if (!response.ok) throw new Error("Failed to add deliverable");
        
        document.getElementById("add-deliv-name").value = "";
        document.getElementById("add-deliv-due").value = "";
        
        if (currentProjectRightAssignment === "โอนสิทธิ์") {
            document.getElementById("add-deliv-internal-no").value = "";
            document.getElementById("add-deliv-external-no").value = "";
        } else {
            document.getElementById("add-deliv-delivery-no").value = "";
        }
        
        openDetailModal(currentProjectId);
    } catch (error) {
        console.error("Error adding deliverable:", error);
        alert("ไม่สามารถเพิ่มรายการส่งมอบได้: " + error.message);
    }
}

async function toggleDeliverableStatus(id, currentStatus) {
    const nextStatus = currentStatus === "ส่งมอบแล้ว" ? "รอดำเนินการ" : "ส่งมอบแล้ว";
    
    try {
        const response = await secureFetch(`/api/deliverables/${id}`, {
            method: "PUT",
            body: JSON.stringify({ status: nextStatus })
        });
        if (!response.ok) throw new Error("Failed to update status");
        
        openDetailModal(currentProjectId);
    } catch (error) {
        console.error("Error toggling status:", error);
        alert("ไม่สามารถเปลี่ยนสถานะงวดงานได้: " + error.message);
    }
}

async function deleteDeliverable(id) {
    if (!confirm("คุณแน่ใจว่าต้องการลบรายการส่งมอบนี้?")) return;
    
    try {
        const response = await secureFetch(`/api/deliverables/${id}`, {
            method: "DELETE"
        });
        if (response.status === 403) {
            const err = await response.json();
            alert(err.detail || "สิทธิ์ไม่เพียงพอสำหรับการลบรายการส่งมอบ");
            return;
        }
        if (!response.ok) throw new Error("Failed to delete deliverable");
        
        openDetailModal(currentProjectId);
    } catch (error) {
        console.error("Error deleting deliverable:", error);
        alert("ไม่สามารถลบรายการส่งมอบได้: " + error.message);
    }
}

// ----------------------------------------------------
// DOCUMENTS SUB-LOGIC
// ----------------------------------------------------
function renderDocumentsList(documents) {
    const list = document.getElementById("detail-documents-list");
    const countBadge = document.getElementById("detail-doc-count");
    
    list.innerHTML = "";
    countBadge.innerText = `${documents.length} ไฟล์`;
    
    if (documents.length === 0) {
        list.innerHTML = `<p class="text-xs text-slate-400 text-center py-4">ยังไม่มีเอกสารแนบโครงการ</p>`;
        return;
    }
    
    const isAdmin = isCurrentUserAdmin();
    
    documents.forEach(doc => {
        // V5 RBAC: Show file delete only for Admin
        const deleteButton = isAdmin 
            ? `
            <button onclick="deleteDocument(${doc.id})" class="text-rose-500 hover:text-rose-700 p-1 rounded hover:bg-rose-50 transition duration-150" title="ลบไฟล์แนบ">
                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
            ` 
            : "";
            
        const docEl = document.createElement("div");
        docEl.className = "bg-slate-50 hover:bg-slate-100 border border-slate-150 p-2.5 rounded-xl flex items-center justify-between text-xs transition duration-150";
        docEl.innerHTML = `
            <div class="flex items-center space-x-2 min-w-0 flex-1">
                <div class="p-1.5 bg-indigo-50 rounded-lg text-indigo-600 font-bold text-[9px] flex-shrink-0 select-none uppercase">
                    ${doc.file_type}
                </div>
                <span class="font-medium text-slate-700 truncate" title="${doc.filename}">${doc.filename}</span>
            </div>
            <div class="flex items-center space-x-1.5 ml-3">
                <a href="${doc.url_path}" target="_blank" download class="text-slate-500 hover:text-slate-700 p-1 rounded hover:bg-slate-200 transition duration-150" title="ดาวน์โหลด">
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                </a>
                ${deleteButton}
            </div>
        `;
        list.appendChild(docEl);
    });
}

async function uploadDetailDocument() {
    const fileInput = document.getElementById("detail-doc-upload-input");
    if (fileInput.files.length === 0) {
        alert("กรุณาเลือกไฟล์เอกสารก่อนกดปุ่มอัปโหลด");
        return;
    }
    
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    
    try {
        const response = await secureFetch(`/api/projects/${currentProjectId}/documents`, {
            method: "POST",
            body: formData
        });
        if (!response.ok) throw new Error("Failed to upload document");
        
        fileInput.value = ""; 
        openDetailModal(currentProjectId); 
    } catch (error) {
        console.error("Error uploading document:", error);
        alert("ไม่สามารถอัปโหลดไฟล์ได้: " + error.message);
    }
}

async function deleteDocument(id) {
    if (!confirm("คุณแน่ใจว่าต้องการลบไฟล์เอกสารแนบนี้?")) return;
    
    try {
        const response = await secureFetch(`/api/documents/${id}`, {
            method: "DELETE"
        });
        if (response.status === 403) {
            const err = await response.json();
            alert(err.detail || "สิทธิ์ไม่เพียงพอสำหรับการลบไฟล์เอกสาร");
            return;
        }
        if (!response.ok) throw new Error("Failed to delete document");
        openDetailModal(currentProjectId); 
    } catch (error) {
        console.error("Error deleting document:", error);
        alert("ไม่สามารถลบไฟล์เอกสารได้: " + error.message);
    }
}

// ----------------------------------------------------
// PURCHASE ORDERS (PO) LOGIC
// ----------------------------------------------------
async function fetchPOs() {
    try {
        const response = await secureFetch("/api/purchase-orders");
        if (!response.ok) throw new Error("Failed to fetch POs");
        posCache = await response.json();
        renderPOsTable(posCache);
    } catch (error) {
        console.error("Error fetching POs:", error);
    }
}

function renderPOsTable(pos) {
    const tableBody = document.getElementById("pos-table-body");
    const noPosMsg = document.getElementById("no-pos-message");
    tableBody.innerHTML = "";
    
    if (pos.length === 0) {
        noPosMsg.classList.remove("hidden");
        return;
    }
    noPosMsg.classList.add("hidden");
    
    const isAdmin = isCurrentUserAdmin();
    
    pos.forEach(po => {
        let badgeColor = "bg-rose-100 text-rose-800";
        if (po.delivery_status === "ส่งมอบแล้ว") {
            badgeColor = "bg-emerald-100 text-emerald-800";
        }
        
        let projName = "ไม่พบข้อมูลโครงการ";
        const linkedProj = projectsCache.find(p => p.id === po.project_id);
        if (linkedProj) projName = linkedProj.name;
        
        // V5 RBAC: Show PO delete button only for Admin
        const deleteButton = isAdmin 
            ? `<button onclick="deletePO(${po.id})" class="text-rose-600 hover:text-rose-900 bg-rose-50 hover:bg-rose-100 px-2.5 py-1.5 rounded-lg transition duration-150">ลบ</button>` 
            : "";
        
        const row = document.createElement("tr");
        row.className = "hover:bg-slate-50/50 transition duration-150";
        row.innerHTML = `
            <td class="px-6 py-4 font-mono font-bold text-indigo-600 text-sm cursor-pointer" onclick="openPODetailModal(${po.id})">${po.po_number}</td>
            <td class="px-6 py-4 font-semibold text-slate-800 text-sm truncate max-w-[280px]" title="${projName}">${projName}</td>
            <td class="px-6 py-4 text-slate-500 text-sm">${po.owner || "-"}</td>
            <td class="px-6 py-4 font-bold text-slate-900 text-sm">${formatCurrency(po.budget)}</td>
            <td class="px-6 py-4 text-slate-500 text-xs">${formatThaiDate(po.due_date)}</td>
            <td class="px-6 py-4 text-slate-600 text-sm">${po.contractor}</td>
            <td class="px-6 py-4">
                <span class="${badgeColor} text-xs px-2.5 py-0.5 rounded-full font-bold">${po.delivery_status}</span>
            </td>
            <td class="px-6 py-4 text-center whitespace-nowrap text-xs font-medium space-x-2">
                <button onclick="openPODetailModal(${po.id})" class="text-indigo-600 hover:text-indigo-900 bg-indigo-50 hover:bg-indigo-100 px-2.5 py-1.5 rounded-lg transition duration-150">ดูรายละเอียด</button>
                <button onclick="editPO(${po.id})" class="text-amber-600 hover:text-amber-900 bg-amber-50 hover:bg-amber-100 px-2.5 py-1.5 rounded-lg transition duration-150">แก้ไข</button>
                ${deleteButton}
            </td>
        `;
        tableBody.appendChild(row);
    });
}

function filterPOs() {
    const searchQuery = document.getElementById("po-search-input").value.toLowerCase();
    const statusFilter = document.getElementById("po-status-filter").value;
    
    const filtered = posCache.filter(po => {
        let projName = "";
        const linkedProj = projectsCache.find(p => p.id === po.project_id);
        if (linkedProj) projName = linkedProj.name;
        
        const matchesSearch = po.po_number.toLowerCase().includes(searchQuery) ||
                             projName.toLowerCase().includes(searchQuery) ||
                             po.contractor.toLowerCase().includes(searchQuery) ||
                             po.material_type.toLowerCase().includes(searchQuery);
                             
        const matchesStatus = statusFilter === "ทั้งหมด" || po.delivery_status === statusFilter;
        
        return matchesSearch && matchesStatus;
    });
    
    renderPOsTable(filtered);
}

// Populate PO Projects select options
function populatePOProjectsDropdown(selectedId = "") {
    const select = document.getElementById("form-po-project-id");
    if (!select) return;
    select.innerHTML = "";
    
    const promptOpt = document.createElement("option");
    promptOpt.value = "";
    promptOpt.innerText = "-- เลือกโครงการหลัก --";
    select.appendChild(promptOpt);
    
    projectsCache.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.innerText = p.name;
        if (p.id == selectedId) opt.selected = true;
        select.appendChild(opt);
    });
}

function autoFillPOOwner() {
    const projId = document.getElementById("form-po-project-id").value;
    if (!projId) {
        document.getElementById("form-po-owner").value = "";
        return;
    }
    const project = projectsCache.find(p => p.id == projId);
    if (project) {
        document.getElementById("form-po-owner").value = project.owner;
    }
}

// V4 Dates Auto-Calculation
function calculatePODueDate() {
    const poDateVal = document.getElementById("form-po-date").value;
    const durationVal = document.getElementById("form-po-duration").value;
    const dueDateInput = document.getElementById("form-po-due-date");
    
    if (poDateVal && durationVal) {
        const poDate = new Date(poDateVal);
        const duration = parseInt(durationVal);
        
        if (!isNaN(poDate.getTime()) && duration > 0) {
            const dueDate = new Date(poDate.getTime() + duration * 24 * 60 * 60 * 1000);
            
            const yyyy = dueDate.getFullYear();
            const mm = String(dueDate.getMonth() + 1).padStart(2, '0');
            const dd = String(dueDate.getDate()).padStart(2, '0');
            dueDateInput.value = `${yyyy}-${mm}-${dd}`;
        }
    }
}

function openPOModal(title = "เพิ่มใบสั่งซื้อใหม่ (PO)") {
    document.getElementById("po-modal-title").innerText = title;
    document.getElementById("po-form").reset();
    document.getElementById("form-po-id").value = "";
    
    populatePOProjectsDropdown();
    populatePOContractorsDropdown();
    populatePOMaterialsDropdown();
    
    document.getElementById("form-po-custom-contractor").value = "";
    document.getElementById("form-po-custom-material").value = "";
    toggleCustomPOContractorInput();
    toggleCustomPOMaterialInput();
    
    document.getElementById("po-modal").classList.remove("hidden");
}

function closePOModal() {
    document.getElementById("po-modal").classList.add("hidden");
}

async function savePO(event) {
    event.preventDefault();
    
    const poId = document.getElementById("form-po-id").value;
    const projectId = document.getElementById("form-po-project-id").value;
    
    if (!projectId) {
        alert("กรุณาเลือกโครงการหลักเพื่อเชื่อมโยงใบสั่งซื้อ");
        return;
    }
    
    let contractorVal = document.getElementById("form-po-contractor").value;
    if (contractorVal === "ADD_NEW") {
        const customName = document.getElementById("form-po-custom-contractor").value.trim();
        if (customName) {
            savePOContractor(customName);
            contractorVal = customName;
        } else {
            alert("กรุณาระบุชื่อบริษัท/ห้างหุ้นส่วนผู้รับผิดชอบ");
            return;
        }
    }
    
    let materialVal = document.getElementById("form-po-material-type").value;
    if (materialVal === "ADD_NEW") {
        const customMat = document.getElementById("form-po-custom-material").value.trim();
        if (customMat) {
            savePOMaterial(customMat);
            materialVal = customMat;
        } else {
            alert("กรุณาระบุประเภทวัสดุ");
            return;
        }
    }
    
    const poData = {
        po_number: document.getElementById("form-po-number").value,
        budget: parseFloat(document.getElementById("form-po-budget").value),
        po_date: document.getElementById("form-po-date").value,
        delivery_duration_days: parseInt(document.getElementById("form-po-duration").value),
        due_date: document.getElementById("form-po-due-date").value,
        owner: document.getElementById("form-po-owner").value,
        contractor: contractorVal,
        material_type: materialVal
    };
    
    try {
        showLoading("กำลังบันทึกข้อมูลใบสั่งซื้อ...");
        let response;
        let savedPO;
        
        if (poId) {
            response = await secureFetch(`/api/purchase-orders/${poId}`, {
                method: "PUT",
                body: JSON.stringify(poData)
            });
            if (!response.ok) throw new Error("Failed to update Purchase Order");
            savedPO = await response.json();
        } else {
            response = await secureFetch(`/api/projects/${projectId}/purchase-orders`, {
                method: "POST",
                body: JSON.stringify(poData)
            });
            if (!response.ok) throw new Error("Failed to create Purchase Order");
            savedPO = await response.json();
        }
        
        const poFileInput = document.getElementById("form-po-file");
        if (poFileInput.files.length > 0) {
            const formData = new FormData();
            formData.append("file", poFileInput.files[0]);
            const uploadResponse = await secureFetch(`/api/purchase-orders/${savedPO.id}/po-file`, {
                method: "POST",
                body: formData
            });
            if (!uploadResponse.ok) throw new Error("Failed to upload PO file");
        }
        
        const quotFileInput = document.getElementById("form-po-quotation-file");
        if (quotFileInput.files.length > 0) {
            const formData = new FormData();
            formData.append("file", quotFileInput.files[0]);
            const uploadResponse = await secureFetch(`/api/purchase-orders/${savedPO.id}/quotation-file`, {
                method: "POST",
                body: formData
            });
            if (!uploadResponse.ok) throw new Error("Failed to upload Quotation file");
        }
        
        closePOModal();
        fetchPOs(); 
    } catch (error) {
        console.error("Error saving PO:", error);
        alert("เกิดข้อผิดพลาดในการบันทึกใบสั่งซื้อ: " + error.message);
    } finally {
        hideLoading();
    }
}

function editPO(id) {
    const po = posCache.find(p => p.id === id);
    if (!po) return;
    
    openPOModal("แก้ไขใบสั่งซื้อ (PO)");
    document.getElementById("form-po-id").value = po.id;
    document.getElementById("form-po-number").value = po.po_number;
    document.getElementById("form-po-budget").value = po.budget;
    document.getElementById("form-po-date").value = po.po_date;
    document.getElementById("form-po-duration").value = po.delivery_duration_days;
    document.getElementById("form-po-due-date").value = po.due_date;
    document.getElementById("form-po-owner").value = po.owner;
    
    populatePOProjectsDropdown(po.project_id);
    
    if (po.contractor) {
        savePOContractor(po.contractor);
        populatePOContractorsDropdown(po.contractor);
    } else {
        populatePOContractorsDropdown();
    }
    
    if (po.material_type) {
        savePOMaterial(po.material_type);
        populatePOMaterialsDropdown(po.material_type);
    } else {
        populatePOMaterialsDropdown();
    }
}

async function deletePO(id) {
    if (!confirm("คุณแน่ใจว่าต้องการลบใบสั่งซื้อ PO นี้? การลบจะรวมถึงการเคลียร์ไฟล์แนบทั้งหมดของ PO นี้")) return;
    
    try {
        showLoading("กำลังลบข้อมูลใบสั่งซื้อ...");
        const response = await secureFetch(`/api/purchase-orders/${id}`, {
            method: "DELETE"
        });
        if (response.status === 403) {
            const err = await response.json();
            alert(err.detail || "สิทธิ์ไม่เพียงพอสำหรับการลบใบสั่งซื้อ");
            return;
        }
        if (!response.ok) throw new Error("Failed to delete PO");
        fetchPOs();
    } catch (error) {
        console.error("Error deleting PO:", error);
        alert("เกิดข้อผิดพลาดในการลบใบสั่งซื้อ: " + error.message);
    } finally {
        hideLoading();
    }
}

// ----------------------------------------------------
// V4 PO DETAIL & DELIVERY Note SUB-LOGIC
// ----------------------------------------------------
async function openPODetailModal(id) {
    currentPOId = id;
    
    try {
        const response = await secureFetch(`/api/purchase-orders/${id}`);
        if (!response.ok) throw new Error("Failed to fetch Purchase Order details");
        const po = await response.json();
        
        let projName = "ไม่พบข้อมูลโครงการ";
        const linkedProj = projectsCache.find(p => p.id === po.project_id);
        if (linkedProj) projName = linkedProj.name;
        
        document.getElementById("detail-po-number").innerText = po.po_number;
        document.getElementById("detail-po-project-name").innerText = `โครงการเชื่อมโยง: ${projName}`;
        
        const statusBadge = document.getElementById("detail-po-delivery-status-badge");
        statusBadge.innerText = po.delivery_status;
        let badgeColor = "bg-rose-100 text-rose-800";
        if (po.delivery_status === "ส่งมอบแล้ว") badgeColor = "bg-emerald-100 text-emerald-800";
        statusBadge.className = `ml-3 px-2.5 py-0.5 rounded-full text-xs font-bold ${badgeColor}`;
        
        document.getElementById("detail-po-budget").innerText = formatCurrency(po.budget);
        document.getElementById("detail-po-date").innerText = formatThaiDate(po.po_date);
        document.getElementById("detail-po-duration").innerText = `${po.delivery_duration_days} วัน`;
        document.getElementById("detail-po-due-date").innerText = formatThaiDate(po.due_date);
        document.getElementById("detail-po-owner").innerText = po.owner;
        document.getElementById("detail-po-contractor").innerText = po.contractor;
        document.getElementById("detail-po-material-type").innerText = po.material_type;
        
        // V5 Audit Trail rendering for PO
        document.getElementById("detail-po-created-by").innerText = po.created_by || "system";
        document.getElementById("detail-po-created-at").innerText = formatTimestamp(po.created_at);
        document.getElementById("detail-po-updated-by").innerText = po.updated_by || "system";
        document.getElementById("detail-po-updated-at").innerText = formatTimestamp(po.updated_at);
        
        renderPOFileContainer(po, 'po-file');
        renderPOFileContainer(po, 'quotation-file');
        
        document.getElementById("detail-po-delivery-no").value = po.delivery_no || "";
        document.getElementById("detail-po-delivery-date").value = po.delivery_date || "";
        document.getElementById("detail-po-delivery-status").value = po.delivery_status || "ยังไม่ได้ส่ง";
        
        renderDeliveryFileContainer(po);
        
        document.getElementById("po-detail-modal").classList.remove("hidden");
    } catch (error) {
        console.error("Error loading PO details:", error);
        alert("ไม่สามารถเปิดรายละเอียด PO ได้: " + error.message);
    }
}

function closePODetailModal() {
    document.getElementById("po-detail-modal").classList.add("hidden");
    currentPOId = null;
    initApp(); 
}

function renderPOFileContainer(po, fileType) {
    let filePath = fileType === 'po-file' ? po.po_file_path : po.quotation_file_path;
    let filename = fileType === 'po-file' ? po.po_file_filename : po.quotation_file_filename;
    
    let container = document.getElementById(fileType === 'po-file' ? "detail-po-file-container" : "detail-po-quotation-file-container");
    let uploadContainer = document.getElementById(fileType === 'po-file' ? "detail-po-file-upload-container" : "detail-po-quotation-file-upload-container");
    
    container.innerHTML = "";
    document.getElementById(fileType === 'po-file' ? "detail-po-file-input" : "detail-po-quotation-input").value = "";
    
    const isAdmin = isCurrentUserAdmin();
    
    if (filePath) {
        uploadContainer.classList.add("hidden");
        
        // V5 RBAC: Show file delete only for Admin
        const deleteButton = isAdmin 
            ? `
            <button onclick="deletePOFile('${fileType}')" class="text-rose-500 hover:text-rose-700 p-1 rounded hover:bg-rose-50 transition duration-150" title="ลบ">
                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
            ` 
            : "";
            
        container.innerHTML = `
            <div class="flex items-center space-x-2 min-w-0 flex-1">
                <svg class="h-4 w-4 text-emerald-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="font-medium text-slate-700 truncate" title="${filename}">${filename}</span>
            </div>
            <div class="flex items-center space-x-1.5 ml-3">
                <a href="${filePath}" target="_blank" download class="text-slate-500 hover:text-slate-700 p-1 rounded hover:bg-slate-100 transition duration-150" title="ดาวน์โหลด">
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                </a>
                ${deleteButton}
            </div>
        `;
    } else {
        uploadContainer.classList.remove("hidden");
        container.innerHTML = `
            <span class="text-slate-400 italic">ยังไม่ได้อัปโหลดไฟล์</span>
        `;
    }
}

async function uploadPOFile(fileType) {
    const inputId = fileType === 'po-file' ? "detail-po-file-input" : "detail-po-quotation-input";
    const fileInput = document.getElementById(inputId);
    if (fileInput.files.length === 0) {
        alert("กรุณาเลือกไฟล์เอกสารก่อนกดปุ่มอัปโหลด");
        return;
    }
    
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    
    const endpoint = fileType === 'po-file' ? "po-file" : "quotation-file";
    try {
        const response = await secureFetch(`/api/purchase-orders/${currentPOId}/${endpoint}`, {
            method: "POST",
            body: formData
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to upload file");
        }
        
        openPODetailModal(currentPOId);
    } catch (error) {
        console.error("Error uploading PO file:", error);
        alert("เกิดข้อผิดพลาดในการอัปโหลดไฟล์: " + error.message);
    }
}

async function deletePOFile(fileType) {
    if (!confirm("คุณแน่ใจว่าต้องการลบไฟล์แนบเอกสารนี้?")) return;
    
    const endpoint = fileType === 'po-file' ? "po-file" : "quotation-file";
    try {
        const response = await secureFetch(`/api/purchase-orders/${currentPOId}/${endpoint}`, {
            method: "DELETE"
        });
        if (response.status === 403) {
            const err = await response.json();
            alert(err.detail || "สิทธิ์ไม่เพียงพอสำหรับการลบไฟล์เอกสาร PO");
            return;
        }
        if (!response.ok) throw new Error("Failed to delete file");
        openPODetailModal(currentPOId);
    } catch (error) {
        console.error("Error deleting file:", error);
        alert("เกิดข้อผิดพลาดในการลบไฟล์: " + error.message);
    }
}

function renderDeliveryFileContainer(po) {
    const fileContainer = document.getElementById("detail-po-delivery-file-container");
    const uploadContainer = document.getElementById("detail-po-delivery-file-upload-container");
    
    fileContainer.innerHTML = "";
    document.getElementById("detail-po-delivery-file-input").value = "";
    
    const isAdmin = isCurrentUserAdmin();
    
    if (po.delivery_file_path) {
        uploadContainer.classList.add("hidden");
        
        // V5 RBAC: Show file delete only for Admin
        const deleteButton = isAdmin 
            ? `
            <button type="button" onclick="deleteDeliveryFile()" class="text-rose-500 hover:text-rose-700 p-1 rounded hover:bg-rose-50 transition duration-150" title="ลบ">
                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
            ` 
            : "";
            
        fileContainer.innerHTML = `
            <div class="flex items-center space-x-2 min-w-0 flex-1">
                <svg class="h-4 w-4 text-emerald-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="font-medium text-slate-700 truncate" title="${po.delivery_file_filename}">${po.delivery_file_filename}</span>
            </div>
            <div class="flex items-center space-x-1.5 ml-3">
                <a href="${po.delivery_file_path}" target="_blank" download class="text-slate-500 hover:text-slate-700 p-1 rounded hover:bg-slate-100 transition duration-150" title="ดาวน์โหลด">
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                </a>
                ${deleteButton}
            </div>
        `;
    } else {
        uploadContainer.classList.remove("hidden");
        fileContainer.innerHTML = `
            <span class="text-slate-400 italic">ยังไม่ได้แนบหลักฐานใบส่งมอบของ</span>
        `;
    }
}

async function deleteDeliveryFile() {
    if (!confirm("คุณแน่ใจว่าต้องการลบไฟล์แนบใบส่งมอบของนี้?")) return;
    
    try {
        const response = await secureFetch(`/api/purchase-orders/${currentPOId}/delivery-file`, {
            method: "DELETE"
        });
        if (response.status === 403) {
            const err = await response.json();
            alert(err.detail || "สิทธิ์ไม่เพียงพอสำหรับการลบไฟล์ใบส่งของ");
            return;
        }
        if (!response.ok) throw new Error("Failed to delete delivery file");
        openPODetailModal(currentPOId);
    } catch (error) {
        console.error("Error deleting file:", error);
        alert("เกิดข้อผิดพลาดในการลบไฟล์: " + error.message);
    }
}

async function savePODelivery(event) {
    event.preventDefault();
    
    const deliveryData = {
        delivery_no: document.getElementById("detail-po-delivery-no").value || null,
        delivery_date: document.getElementById("detail-po-delivery-date").value || null,
        delivery_status: document.getElementById("detail-po-delivery-status").value
    };
    
    try {
        showLoading("กำลังบันทึกข้อมูลการส่งมอบ...");
        const response = await secureFetch(`/api/purchase-orders/${currentPOId}`, {
            method: "PUT",
            body: JSON.stringify(deliveryData)
        });
        
        if (!response.ok) throw new Error("Failed to update delivery status");
        
        const fileInput = document.getElementById("detail-po-delivery-file-input");
        if (fileInput.files.length > 0) {
            const formData = new FormData();
            formData.append("file", fileInput.files[0]);
            
            const uploadResponse = await secureFetch(`/api/purchase-orders/${currentPOId}/delivery-file`, {
                method: "POST",
                body: formData
            });
            
            if (!uploadResponse.ok) {
                const err = await uploadResponse.json();
                throw new Error(err.detail || "Failed to upload delivery note file");
            }
        }
        
        alert("บันทึกการส่งมอบเรียบร้อย");
        openPODetailModal(currentPOId);
    } catch (error) {
        console.error("Error saving delivery:", error);
        alert("เกิดข้อผิดพลาดในการบันทึก: " + error.message);
    } finally {
        hideLoading();
    }
}

// ----------------------------------------------------
// USER MANAGEMENT SECTION (ADMIN ONLY V5 RBAC)
// ----------------------------------------------------
async function fetchUsers() {
    try {
        const response = await secureFetch("/api/users");
        if (!response.ok) throw new Error("Failed to fetch users list");
        const users = await response.json();
        renderUsersTable(users);
    } catch (error) {
        console.error("Error fetching users:", error);
    }
}

function renderUsersTable(users) {
    const tbody = document.getElementById("users-table-body");
    tbody.innerHTML = "";
    
    const currentUser = JSON.parse(localStorage.getItem("current_user") || "{}");
    
    users.forEach(u => {
        const isSelf = u.id === currentUser.id;
        
        // Active Toggle Switch
        const activeToggle = isSelf 
            ? `<span class="text-xs text-slate-400 italic font-semibold">บัญชีของคุณ</span>` 
            : `
            <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" ${u.is_active ? 'checked' : ''} onclick="toggleUserActive(${u.id})" class="sr-only peer">
                <div class="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
            </label>
            `;
            
        // Reset Password Button
        const changePwdBtn = `
            <button onclick="openResetPasswordModal(${u.id}, '${u.username}')" class="text-amber-600 hover:text-amber-900 bg-amber-50 hover:bg-amber-100 px-2.5 py-1.5 rounded-lg transition duration-150 flex items-center gap-1 font-semibold">
                <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 7a2 2 0 012 2m-2-2a2 2 0 00-2 2m2-2a2 2 0 002 2m0 0V19a2 2 0 01-2 2h-3a2 2 0 01-2-2v-3a2 2 0 00-2-2H9a2 2 0 00-2-2V9a2 2 0 012-2h6z" />
                </svg>
                แก้ไขรหัสผ่าน
            </button>
        `;
            
        // Delete button
        const deleteBtn = isSelf 
            ? "" 
            : `<button onclick="deleteUser(${u.id}, '${u.username}')" class="text-rose-600 hover:text-rose-900 bg-rose-50 hover:bg-rose-100 px-2.5 py-1.5 rounded-lg transition duration-150 font-semibold">ลบ</button>`;
            
        const statusBadge = u.is_active 
            ? `<span class="bg-emerald-100 text-emerald-800 text-xs px-2.5 py-0.5 rounded-full font-bold">ปกติ</span>`
            : `<span class="bg-slate-100 text-slate-500 text-xs px-2.5 py-0.5 rounded-full font-semibold">ถูกระงับสิทธิ์</span>`;
            
        const row = document.createElement("tr");
        row.className = "hover:bg-slate-50 transition duration-150 text-xs";
        row.innerHTML = `
            <td class="px-6 py-4 font-semibold text-slate-500">${u.id}</td>
            <td class="px-6 py-4 font-mono font-semibold text-slate-800">${u.username}</td>
            <td class="px-6 py-4 font-medium text-slate-900">${u.fullname}</td>
            <td class="px-6 py-4">
                <span class="px-2 py-0.5 rounded-full font-bold text-[10px] uppercase ${u.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-slate-100 text-slate-600'}">
                    ${u.role}
                </span>
            </td>
            <td class="px-6 py-4">${statusBadge}</td>
            <td class="px-6 py-4 flex items-center gap-2 justify-center">
                <div class="flex items-center gap-2 mr-2">${activeToggle}</div>
                ${changePwdBtn}
                ${deleteBtn}
            </td>
        `;
        tbody.appendChild(row);
    });
}

function openResetPasswordModal(userId, username) {
    document.getElementById("reset-pwd-user-id").value = userId;
    document.getElementById("reset-pwd-username-display").innerText = username;
    document.getElementById("reset-pwd-new-password").value = "";
    document.getElementById("reset-password-modal").classList.remove("hidden");
}

function closeResetPasswordModal() {
    document.getElementById("reset-password-modal").classList.add("hidden");
}

async function submitResetPassword(event) {
    event.preventDefault();
    const userId = document.getElementById("reset-pwd-user-id").value;
    const newPassword = document.getElementById("reset-pwd-new-password").value;
    
    try {
        const response = await secureFetch(`/api/users/${userId}/reset-password`, {
            method: "PUT",
            body: JSON.stringify({ new_password: newPassword })
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to reset password");
        }
        
        alert("เปลี่ยนรหัสผ่านสำหรับผู้ใช้งานสำเร็จ!");
        closeResetPasswordModal();
        fetchUsers();
    } catch (error) {
        console.error("Error resetting password:", error);
        alert("เกิดข้อผิดพลาดในการเปลี่ยนรหัสผ่าน: " + error.message);
    }
}

async function toggleUserActive(userId) {
    try {
        const response = await secureFetch(`/api/users/${userId}/toggle-active`, {
            method: "PUT"
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to toggle active status");
        }
        fetchUsers();
    } catch (error) {
        console.error("Error toggling user active status:", error);
        alert(error.message);
    }
}

async function deleteUser(userId, username) {
    if (!confirm(`คุณต้องการลบผู้ใช้งาน "${username}" ออกจากระบบใช่หรือไม่?`)) return;
    
    try {
        const response = await secureFetch(`/api/users/${userId}`, {
            method: "DELETE"
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to delete user");
        }
        fetchUsers();
    } catch (error) {
        console.error("Error deleting user:", error);
        alert(error.message);
    }
}

async function fetchAuditLogs() {
    try {
        const response = await secureFetch("/api/audit-logs");
        if (!response.ok) throw new Error("Failed to fetch audit logs");
        const logs = await response.json();
        renderAuditLogsTable(logs);
        
        // Update subtitle based on user role
        const currentUser = JSON.parse(localStorage.getItem("current_user") || "{}");
        const subtitle = document.getElementById("audit-logs-subtitle");
        if (currentUser.role === "admin") {
            subtitle.innerText = "สิทธิ์แอดมิน: ตรวจสอบประวัติกิจกรรมทั้งหมดของผู้ใช้ทุกคนในระบบ";
        } else {
            subtitle.innerText = "ประวัติกิจกรรมทั้งหมดที่คุณได้ทำรายการไว้ในระบบ (แสดงเฉพาะของคุณเอง)";
        }
    } catch (error) {
        console.error("Error fetching audit logs:", error);
    }
}

function renderAuditLogsTable(logs) {
    const tbody = document.getElementById("audit-logs-table-body");
    tbody.innerHTML = "";
    
    if (logs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="px-6 py-8 text-center text-slate-400">
                    <svg class="h-8 w-8 mx-auto text-slate-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    ยังไม่มีบันทึกประวัติกิจกรรมในระบบ
                </td>
            </tr>
        `;
        return;
    }
    
    logs.forEach(log => {
        const row = document.createElement("tr");
        row.className = "hover:bg-slate-50 transition duration-150 text-xs";
        
        // Action badge styling
        let actionBadge = "";
        if (log.action === "สร้าง") {
            actionBadge = `<span class="bg-emerald-100 text-emerald-800 text-[10px] px-2 py-0.5 rounded font-bold">สร้าง</span>`;
        } else if (log.action === "แก้ไข") {
            actionBadge = `<span class="bg-amber-100 text-amber-800 text-[10px] px-2 py-0.5 rounded font-bold">แก้ไข</span>`;
        } else if (log.action === "ลบ") {
            actionBadge = `<span class="bg-rose-100 text-rose-800 text-[10px] px-2 py-0.5 rounded font-bold">ลบ</span>`;
        } else {
            actionBadge = `<span class="bg-slate-100 text-slate-700 text-[10px] px-2 py-0.5 rounded font-bold">${log.action}</span>`;
        }
        
        // Item type badge styling
        let itemBadge = `<span class="bg-indigo-50 text-indigo-750 text-[10px] px-2 py-0.5 rounded font-medium text-indigo-700 bg-indigo-100/50">${log.target_type}</span>`;
        
        row.innerHTML = `
            <td class="px-6 py-4 font-semibold text-slate-500 whitespace-nowrap">${formatTimestamp(log.timestamp)}</td>
            <td class="px-6 py-4">
                <div class="font-medium text-slate-900">${log.fullname || "-"}</div>
                <div class="text-[10px] font-mono text-slate-400">${log.username}</div>
            </td>
            <td class="px-6 py-4">${actionBadge}</td>
            <td class="px-6 py-4">${itemBadge}</td>
            <td class="px-6 py-4 font-semibold text-slate-800">${log.target_name || "-"}</td>
            <td class="px-6 py-4 text-slate-650 font-medium text-slate-600">${log.details || "-"}</td>
        `;
        tbody.appendChild(row);
    });
}

// ----------------------------------------------------
// UTILITY FUNCTIONS
// ----------------------------------------------------
function formatCurrency(amount) {
    return new Intl.NumberFormat("th-TH", {
        style: "currency",
        currency: "THB"
    }).format(amount);
}

function formatThaiDate(dateString) {
    if (!dateString) return "-";
    const date = new Date(dateString);
    if (isNaN(date)) return dateString;
    
    return date.toLocaleDateString("th-TH", {
        day: "numeric",
        month: "short",
        year: "numeric"
    });
}

function formatTimestamp(timestampString) {
    if (!timestampString) return "-";
    const date = new Date(timestampString);
    if (isNaN(date)) return timestampString;
    
    return date.toLocaleDateString("th-TH", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
}
