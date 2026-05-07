function initResumeCounter() {
    const resumeField = document.querySelector('textarea[name="resume"]');
    const resumeCount = document.getElementById("resumeCount");
    
    if (resumeField && resumeCount) {
        resumeCount.textContent = resumeField.value.length;
        
        resumeField.addEventListener("input", function() {
            resumeCount.textContent = this.value.length;
        });
    }
}

function deleteExistingForm(button) {
    const formCard = button.closest('.education-form, .experience-form, .skill-form');
    if (!formCard) return false;
    
    const deleteCheckbox = formCard.querySelector('[name*=DELETE]');
    if (deleteCheckbox) {
        deleteCheckbox.checked = true;
    }
    formCard.style.display = 'none';
    return false;
}

function deleteNewForm(button) {
    const formCard = button.closest('.education-form, .experience-form, .skill-form');
    if (formCard) {
        formCard.remove();
    }
    return false;
}

function addEducationForm() {
    const formsetContainer = document.getElementById("education-formset");
    const managementForm = document.querySelector('[name="education-TOTAL_FORMS"]');
    
    if (!formsetContainer || !managementForm) return;
    
    const formCount = parseInt(managementForm.value);
    const newFormHTML = createEducationForm(formCount);
    
    const newForm = document.createElement("div");
    newForm.className = "education-form mb-4 p-3 border rounded position-relative";
    newForm.innerHTML = newFormHTML;
    
    const deleteBtn = newForm.querySelector(".btn-delete-form");
    deleteBtn.addEventListener("click", function(e) {
        e.preventDefault();
        deleteNewForm(this);
    });
    
    formsetContainer.appendChild(newForm);
    managementForm.value = formCount + 1;
}


function createEducationForm(index) {
    return `
        <button type="button" class="btn btn-sm btn-danger btn-delete-form position-absolute" style="top: 10px; right: 10px;">
            <i class="bi bi-trash"></i>
        </button>
        <div class="row">
            <div class="col-md-6 mb-3">
                <label class="form-label fw-bold text-muted small text-uppercase">
                    Școala/Facultatea
                </label>
                <input type="text" name="education-${index}-school_name" class="form-control">
            </div>
            <div class="col-md-3 mb-3">
                <label class="form-label fw-bold text-muted small text-uppercase">
                    Data de început
                </label>
                <input type="date" name="education-${index}-start_date" class="form-control">
            </div>
            <div class="col-md-3 mb-3">
                <label class="form-label fw-bold text-muted small text-uppercase">
                    Data de sfârşit
                </label>
                <input type="date" name="education-${index}-end_date" class="form-control">
            </div>
        </div>
        <div class="row">
            <div class="col-12 mb-3">
                <label class="form-label fw-bold text-muted small text-uppercase">
                    Detalii
                </label>
                <textarea name="education-${index}-details" class="form-control" rows="3"></textarea>
            </div>
        </div>
    `;
}


function addExperienceForm() {
    const formsetContainer = document.getElementById("experience-formset");
    const managementForm = document.querySelector('[name="experience-TOTAL_FORMS"]');
    
    if (!formsetContainer || !managementForm) return;
    
    const formCount = parseInt(managementForm.value);
    const newFormHTML = createExperienceForm(formCount);
    
    const newForm = document.createElement("div");
    newForm.className = "experience-form mb-4 p-3 border rounded position-relative";
    newForm.innerHTML = newFormHTML;
    
    const deleteBtn = newForm.querySelector(".btn-delete-form");
    deleteBtn.addEventListener("click", function(e) {
        e.preventDefault();
        deleteNewForm(this);
    });
    
    formsetContainer.appendChild(newForm);
    managementForm.value = formCount + 1;
}


function createExperienceForm(index) {
    return `
        <button type="button" class="btn btn-sm btn-danger btn-delete-form position-absolute" style="top: 10px; right: 10px;">
            <i class="bi bi-trash"></i>
        </button>
        <div class="row">
            <div class="col-md-6 mb-3">
                <label class="form-label fw-bold text-muted small text-uppercase">
                    Instituție/Companie
                </label>
                <input type="text" name="experience-${index}-institution_name" class="form-control">
            </div>
            <div class="col-md-3 mb-3">
                <label class="form-label fw-bold text-muted small text-uppercase">
                    Data de început
                </label>
                <input type="date" name="experience-${index}-start_date" class="form-control">
            </div>
            <div class="col-md-3 mb-3">
                <label class="form-label fw-bold text-muted small text-uppercase">
                    Data de sfârşit
                </label>
                <input type="date" name="experience-${index}-end_date" class="form-control">
            </div>
        </div>
        <div class="row">
            <div class="col-12 mb-3">
                <label class="form-label fw-bold text-muted small text-uppercase">
                    Detalii
                </label>
                <textarea name="experience-${index}-details" class="form-control" rows="3"></textarea>
            </div>
        </div>
    `;
}


function addSkillForm() {
    const formsetContainer = document.getElementById("skill-formset");
    const managementForm = document.querySelector('[name="skill-TOTAL_FORMS"]');
    
    if (!formsetContainer || !managementForm) return;
    
    const formCount = parseInt(managementForm.value);
    const newFormHTML = createSkillForm(formCount);
    
    const newForm = document.createElement("div");
    newForm.className = "skill-form mb-3 p-3 border rounded position-relative";
    newForm.innerHTML = newFormHTML;
    
    const deleteBtn = newForm.querySelector(".btn-delete-form");
    deleteBtn.addEventListener("click", function(e) {
        e.preventDefault();
        deleteNewForm(this);
    });
    
    formsetContainer.appendChild(newForm);
    managementForm.value = formCount + 1;
}


function createSkillForm(index) {
    return `
        <button type="button" class="btn btn-sm btn-danger btn-delete-form position-absolute" style="top: 10px; right: 10px;">
            <i class="bi bi-trash"></i>
        </button>
        <div class="row">
            <div class="col-md-6 mb-3">
                <label class="form-label fw-bold text-muted small text-uppercase">
                    Tip Abilitate
                </label>
                <select name="skill-${index}-skill_type" class="form-control">
                    <option value="">-- Selectează tip --</option>
                    <option value="program">Program/Software</option>
                    <option value="language">Limbaj de programare</option>
                    <option value="foreign_language">Limbă străină</option>
                    <option value="soft_skill">Soft Skill</option>
                </select>
            </div>
            <div class="col-md-6 mb-3">
                <label class="form-label fw-bold text-muted small text-uppercase">
                    Abilitate
                </label>
                <input type="text" name="skill-${index}-skill_name" class="form-control">
            </div>
        </div>
    `;
}


document.addEventListener("DOMContentLoaded", function() {
    initResumeCounter();
});
