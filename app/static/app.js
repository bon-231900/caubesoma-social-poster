const { createApp } = Vue;

createApp({
  data() {
    return {
      isAuthenticated: false,
      currentUserRole: 'admin',
      authToken: '',
      loginPassword: '',
      showLoginPassword: false,
      loginError: '',
      isLoggingIn: false,
      pendingPosts: [],

      activeTab: 'composer',
      captionTab: 'fb',
      previewPlatform: 'fb',
      currentIgPreviewIdx: 0,
      isDragging: false,
      isDraggingBulk: false,
      isSubmitting: false,
      isTesting: false,
      isSaving: false,
      isImportingBulk: false,
      isGeneratingStory: false,
      isGeneratingAiHook: false,
      showToken: false,
      storyMode: 'custom',
      isDraggingStory: false,
      isUploadingStoryImage: false,

      // AI Box State
      aiUserHint: '',
      isAiGenerating: false,

      postForm: {
        target_fb: true,
        target_ig: true,
        target_story: true,
        target_google: false,
        target_threads: false,
        story_template: 'organic',
        story_hook: '',
        story_link: 'https://roots.vn',
        story_image: '',
        images: [],
        fb_caption: '',
        ig_caption: '',
        google_caption: '',
        threads_caption: '',
        threads_topic_tag: '',
        google_action_type: 'LEARN_MORE',
        google_action_url: 'https://roots.vn',
        action: 'now',
        scheduled_time: ''
      },
      threadsProfile: {
        connected: false,
        username: 'roots.vn',
        user_id: '',
        profile_picture: '',
        biography: '',
        error: null
      },
      threadsTopicsList: [],
      showThreadsTopicDropdown: false,
      isSearchingTopics: false,
      bulkPreviewPosts: [],
      scheduledPosts: [],
      historyPosts: [],
      
      settingsForm: {
        fb_page_id: '',
        fb_page_access_token: '',
        ig_business_account_id: '',
        threads_app_id: '',
        threads_app_secret: '',
        threads_user_id: '',
        threads_access_token: '',
        has_threads_token: false,
        has_threads_app_secret: false,
        imgbb_api_key: '',
        gemini_api_key: '',
        gemini_model: 'gemini-3.5-flash-lite',
        google_client_id: '',
        google_client_secret: '',
        google_connected: false,
        google_location_name: '',
        google_location_id: '',
        google_logo_url: 'https://roots.vn/images/favicon-180x180.png',
        google_rating: '4.9',
        google_review_count: '150+',
        isSyncingGoogle: false,
        has_fb_page_access_token: false,
        has_imgbb_api_key: false,
        has_gemini_api_key: false,
        has_google_client_secret: false,
        has_admin_password: false,
        has_staff_password: false,
        app_password: '',
        admin_password: '',
        staff_password: '',
        max_upload_mb: 12,
        max_upload_batch_mb: 48,
        media_retention_days: 90
      },

      metaStatus: {
        facebook: { connected: false, page_name: 'ROOTS - Organic Store & Juice Bar', page_id: '', picture: '', error: '' },
        instagram: { connected: false, username: 'rootsvn.official', account_id: '', profile_picture: '', error: '' }
      },

      // ROOTS Catalog
      rootsProducts: [],
      rootsCategories: {},
      selectedRootsCategory: 'all',
      rootsSearchQuery: '',
      isLoadingRoots: false,
      isGenerating1Click: false,
      generatingProductId: null,
      rootsPagination: {
        current_page: 1,
        total_pages: 1,
        total_items: 0
      },
      selectedComboProducts: [],
      comboModal: {
        show: false,
        isLoading: false,
        result: null,
        activeCaptionTab: 'fb',
        copiedPromptIdx: null
      },

      mediaLibrary: [],
      selectedMediaTag: 'all',
      mediaSearchQuery: '',
      isLoadingMedia: false,

      hashtagGroups: [],
      selectedHashtagGroupId: '',
      newHashtagName: '',
      newHashtagContent: '',
      newHashtagCategory: 'Hữu cơ',

      captionTemplates: [],
      selectedTemplateId: '',
      newTemplateName: '',
      newTemplateContent: '',
      newTemplateCategory: 'Sản phẩm',
      newTemplateVoice: 'Bán hàng',

      calendarEvents: [],
      selectedCalendarPost: null,
      showCalendarModal: false,
      calendarModalCaptionTab: 'fb',
      calendarFilterPlatform: 'all',
      calendarFilterStatus: 'all',
      calendarViewMode: 'month',
      calendarCurrentYear: new Date().getFullYear(),
      calendarCurrentMonth: new Date().getMonth(),

      toast: {
        show: false,
        message: '',
        type: 'success'
      },
      cronEndpointUrl: (typeof window !== 'undefined' && window.location.origin ? window.location.origin : 'https://caubesoma-poster.onrender.com') + '/api/cron/check-due'
    };
  },

  async mounted() {
    await this.checkAuth();
    const params = new URLSearchParams(window.location.search);
    if (params.get('threads_connected') === 'success') {
      this.showToast('🎉 Đã liên kết tài khoản Meta Threads @roots.vn thành công!', 'success');
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (params.get('threads_error')) {
      this.showToast('⚠️ Lỗi liên kết Threads: ' + params.get('threads_error'), 'error');
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);
    this.postForm.scheduled_time = tomorrow.toISOString().slice(0, 16);
  },

  methods: {
    async authFetch(url, options = {}) {
      if (!options.headers) options.headers = {};
      options.credentials = 'same-origin';
      const res = await fetch(url, options);
      if (res.status === 401) {
        this.isAuthenticated = false;
      }
      return res;
    },

    async checkAuth() {
      try {
        const res = await fetch('/api/auth/check', { credentials: 'same-origin' });
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated) {
            this.isAuthenticated = true;
            this.currentUserRole = data.role || 'staff';
            if (this.currentUserRole === 'admin') {
              this.loadSettings();
            }
            this.loadMetaStatus();
            this.loadThreadsStatus();
            this.fetchThreadsTopics();
            this.loadScheduledPosts();
            this.loadPendingPosts();
            this.loadRootsCategories();
            this.loadRootsData();
            this.loadMediaLibrary();
            this.loadTemplatesAndHashtags();
            this.loadCalendarEvents();
            return;
          }
        }
        this.isAuthenticated = false;
      } catch (e) {
        this.isAuthenticated = false;
      }
    },

    async handleLogin() {
      this.isLoggingIn = true;
      this.loginError = '';
      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: this.loginPassword })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.isAuthenticated = true;
          this.currentUserRole = data.role || 'staff';
          this.loginPassword = '';
          const roleLabel = this.currentUserRole === 'admin' ? '👑 Quản Trị Viên (Admin)' : '🧑‍💼 Nhân Viên (Staff)';
          this.showToast(`Đăng nhập thành công với quyền ${roleLabel}!`, 'success');
          if (this.currentUserRole === 'admin') {
            this.loadSettings();
          }
          this.loadMetaStatus();
          this.loadScheduledPosts();
          this.loadPendingPosts();
          this.loadRootsCategories();
          this.loadRootsData();
          this.loadMediaLibrary();
          this.loadTemplatesAndHashtags();
          this.loadCalendarEvents();
        } else {
          this.loginError = data.detail || 'Mật khẩu không chính xác';
        }
      } catch (err) {
        this.loginError = 'Lỗi kết nối máy chủ: ' + err.message;
      } finally {
        this.isLoggingIn = false;
      }
    },

    async handleLogout() {
      if (confirm('Bạn có chắc chắn muốn đăng xuất?')) {
        try {
          await this.authFetch('/api/auth/logout', { method: 'POST' });
        } catch (e) {}
        this.isAuthenticated = false;
        this.showToast('Đã đăng xuất', 'info');
      }
    },

    showToast(message, type = 'success') {
      this.toast.message = message;
      this.toast.type = type;
      this.toast.show = true;
      setTimeout(() => {
        this.toast.show = false;
      }, 4000);
    },

    // ── UPLOAD IMAGES ──
    async uploadFiles(fileList) {
      if (!fileList || fileList.length === 0) return;
      const formData = new FormData();
      for (let i = 0; i < fileList.length; i++) {
        formData.append('files', fileList[i]);
      }
      try {
        const res = await this.authFetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (res.ok && data.success) {
          const filenames = data.filenames || (data.uploaded ? data.uploaded.map(u => u.filename) : []);
          this.postForm.images.push(...filenames);
          this.showToast(`Đã tải lên ${filenames.length} ảnh thành công!`, 'success');
          this.loadMediaLibrary();
          if (this.postForm.target_story && this.postForm.images.length > 0 && !this.postForm.story_image && this.storyMode === 'template') {
            this.generateStoryPreview();
          }
        } else {
          this.showToast(data.detail || 'Lỗi tải ảnh', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối tải ảnh: ' + e.message, 'error');
      }
    },

    handleFileDrop(e) {
      this.isDragging = false;
      if (e.dataTransfer && e.dataTransfer.files) {
        this.uploadFiles(e.dataTransfer.files);
      }
    },

    handleFileInput(e) {
      if (e.target.files) {
        this.uploadFiles(e.target.files);
      }
    },

    // ── CUSTOM STORY 9:16 UPLOAD ──
    async uploadStoryFile(file) {
      if (!file) return;
      this.isUploadingStoryImage = true;
      const formData = new FormData();
      formData.append('files', file);
      try {
        const res = await this.authFetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (res.ok && data.success) {
          const filenames = data.filenames || (data.uploaded ? data.uploaded.map(u => u.filename) : []);
          if (filenames.length > 0) {
            this.postForm.story_image = filenames[0];
            this.postForm.target_story = true;
            this.storyMode = 'custom';
            this.previewPlatform = 'story';
            this.showToast('✨ Đã tải lên ảnh Story 9:16 riêng thành công!', 'success');
            this.loadMediaLibrary();
          }
        } else {
          this.showToast(data.detail || 'Lỗi tải ảnh Story', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi tải ảnh Story: ' + e.message, 'error');
      } finally {
        this.isUploadingStoryImage = false;
      }
    },

    handleStoryFileInput(e) {
      if (e.target.files && e.target.files[0]) {
        this.uploadStoryFile(e.target.files[0]);
      }
    },

    handleStoryFileDrop(e) {
      this.isDraggingStory = false;
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        this.uploadStoryFile(e.dataTransfer.files[0]);
      }
    },

    removeStoryImage() {
      this.postForm.story_image = '';
      this.showToast('Đã gỡ ảnh Story 9:16.', 'info');
    },

    useMediaAsStory(filename) {
      this.postForm.story_image = filename;
      this.postForm.target_story = true;
      this.storyMode = 'custom';
      this.activeTab = 'composer';
      this.previewPlatform = 'story';
      this.showToast('✨ Đã chọn ảnh làm Story 9:16!', 'success');
    },

    removeImage(idx) {
      this.postForm.images.splice(idx, 1);
      if (this.postForm.images.length === 0) {
        if (this.storyMode === 'template') {
          this.postForm.story_image = '';
        }
      } else if (this.postForm.target_story && this.storyMode === 'template') {
        this.generateStoryPreview();
      }
    },

    useMediaInComposer(filename) {
      if (!this.postForm.images.includes(filename)) {
        this.postForm.images.push(filename);
        this.showToast('Đã thêm ảnh vào bài viết!', 'success');
        this.activeTab = 'composer';
        if (this.postForm.target_story && this.storyMode === 'template' && !this.postForm.story_image) {
          this.generateStoryPreview();
        }
      } else {
        this.showToast('Ảnh này đã có trong bài viết.', 'info');
      }
    },

    async deleteMediaItem(filename) {
      if (!confirm('Bạn có chắc muốn xóa ảnh này khỏi thư viện?')) return;
      try {
        const res = await this.authFetch(`/api/media/${filename}`, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa ảnh thành công', 'info');
          this.loadMediaLibrary();
        }
      } catch (e) {}
    },

    getMediaUrl(filename) {
      if (!filename) return '';
      if (filename.startsWith('http://') || filename.startsWith('https://')) return filename;
      return `/api/media/${filename}`;
    },

    // ── AI CAPTION ASSISTANT ──
    setAiHint(promptText) {
      this.aiUserHint = promptText;
      this.generateAICaption();
    },

    async generateAICaption() {
      this.isAiGenerating = true;
      try {
        const res = await this.authFetch('/api/ai/generate-caption', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ images: this.postForm.images, user_hint: this.aiUserHint })
        });
        const data = await res.json();
        if (res.ok && data.data) {
          this.postForm.fb_caption = data.data.fb_caption || data.data.facebook || '';
          this.postForm.ig_caption = data.data.ig_caption || data.data.instagram || '';
          this.postForm.google_caption = data.data.google_caption || data.data.google || '';
          this.postForm.threads_caption = data.data.threads_caption || data.data.threads || '';
          if (data.data.story_hook) {
            this.postForm.story_hook = data.data.story_hook;
          }
          this.showToast('✨ Gemini AI đã tạo xong 4 Caption chuẩn phong cách ROOTS (kèm Threads)!', 'success');
          if (this.postForm.target_story && this.postForm.images.length > 0) {
            this.generateStoryPreview();
          }
        } else {
          this.showToast(data.detail || 'Lỗi tạo Caption AI', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối AI: ' + e.message, 'error');
      } finally {
        this.isAiGenerating = false;
      }
    },

    // ── STORY DESIGNER GENERATOR ──
    async generateStoryPreview(templateName = null) {
      if (templateName) {
        this.postForm.story_template = templateName;
      }
      if (!this.postForm.images || this.postForm.images.length === 0) {
        this.showToast('Vui lòng tải lên ít nhất 1 ảnh để tạo mẫu Story 9:16', 'info');
        return;
      }
      this.isGeneratingStory = true;
      try {
        const res = await this.authFetch('/api/story/preview-generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image_name: this.postForm.images[0],
            caption: this.postForm.fb_caption || this.aiUserHint || '',
            template: this.postForm.story_template || 'organic',
            hook: this.postForm.story_hook || this.postForm.fb_caption || '',
            link: this.postForm.story_link || 'https://roots.vn'
          })
        });
        const data = await res.json();
        if (res.ok && data.story_image) {
          this.postForm.story_image = data.story_image;
          this.showToast(`✨ Đã áp dụng mẫu thiết kế Story 9:16 (${this.getTemplateLabel(this.postForm.story_template)})!`, 'success');
        } else {
          this.showToast(data.detail || 'Không thể tạo mẫu Story', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi khi thiết kế Story: ' + e.message, 'error');
      } finally {
        this.isGeneratingStory = false;
      }
    },

    getTemplateLabel(tpl) {
      const map = {
        organic: '🌿 Hữu cơ Organic',
        juice: '🍹 Nước ép Detox',
        sale: '🔥 Flash Sale',
        editorial: '✨ Tạp chí Sang trọng',
        polaroid: '⭐ Review Bán chạy'
      };
      return map[tpl] || tpl;
    },

    getGoogleCtaLabel(type) {
      const map = {
        LEARN_MORE: 'Tìm hiểu thêm',
        ORDER: 'Đặt hàng ngay',
        BOOK: 'Đặt chỗ ngay',
        SHOP: 'Mua sắm ngay',
        SIGN_UP: 'Đăng ký ngay',
        CALL: 'Gọi ngay: 0868 472 236',
        NONE: 'Không nút'
      };
      return map[type] || 'Tìm hiểu thêm';
    },

    // ── THREADS TOPICS & COMMUNITIES AUTOCOMPLETE ──
    removeAccents(str) {
      if (!str) return '';
      return str.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();
    },

    async fetchThreadsTopics(query = '') {
      try {
        const url = query ? `/api/threads/topics?q=${encodeURIComponent(query)}` : '/api/threads/topics';
        const res = await this.authFetch(url);
        if (res.ok) {
          const data = await res.json();
          this.threadsTopicsList = data.topics || [];
        }
      } catch (e) {
        console.error('Error fetching Threads topics:', e);
      }
    },

    onThreadsTopicInput() {
      this.showThreadsTopicDropdown = true;
      this.isSearchingTopics = true;
      clearTimeout(this._topicSearchTimer);
      const q = (this.postForm.threads_topic_tag || '').trim();
      this._topicSearchTimer = setTimeout(async () => {
        try {
          await this.fetchThreadsTopics(q);
        } finally {
          this.isSearchingTopics = false;
        }
      }, 160);
    },

    getFilteredThreadsTopics() {
      const qRaw = (this.postForm.threads_topic_tag || '').trim().toLowerCase();
      if (!qRaw) {
        return this.threadsTopicsList.slice(0, 35);
      }
      const qNorm = this.removeAccents(qRaw);
      const qNoSpace = qNorm.replace(/\s+/g, '');
      const filtered = this.threadsTopicsList.filter(t => {
        const nameRaw = (t.name || '').toLowerCase();
        const nameNorm = this.removeAccents(t.name || '');
        const nameNoSpace = nameNorm.replace(/\s+/g, '');
        const catRaw = (t.category || '').toLowerCase();
        const catNorm = this.removeAccents(t.category || '');
        return nameRaw.includes(qRaw) || nameNorm.includes(qNorm) || nameNoSpace.includes(qNoSpace) || qNoSpace.includes(nameNoSpace) || catRaw.includes(qRaw) || catNorm.includes(qNorm);
      });
      return (filtered.length > 0 ? filtered : this.threadsTopicsList).slice(0, 35);
    },

    hasExactTopicMatch() {
      const qRaw = (this.postForm.threads_topic_tag || '').trim().toLowerCase();
      if (!qRaw) return true;
      const qNorm = this.removeAccents(qRaw);
      const qNoSpace = qNorm.replace(/\s+/g, '');
      return this.threadsTopicsList.some(t => {
        const nameRaw = (t.name || '').toLowerCase();
        const nameNorm = this.removeAccents(t.name || '');
        const nameNoSpace = nameNorm.replace(/\s+/g, '');
        return nameRaw === qRaw || nameNorm === qNorm || nameNoSpace === qNoSpace;
      });
    },

    selectThreadsTopic(name) {
      this.postForm.threads_topic_tag = name;
      this.showThreadsTopicDropdown = false;
      this.showToast(`Đã chọn chủ đề: "${name}"`, 'info');
    },

    selectFirstOrNewTopic() {
      const filtered = this.getFilteredThreadsTopics();
      if (filtered.length > 0) {
        this.selectThreadsTopic(filtered[0].name);
      } else if (this.postForm.threads_topic_tag) {
        this.createAndSelectNewTopic(this.postForm.threads_topic_tag);
      }
    },

    clearThreadsTopic() {
      this.postForm.threads_topic_tag = '';
      this.showThreadsTopicDropdown = false;
      this.fetchThreadsTopics();
    },

    async createAndSelectNewTopic(name) {
      const cleanName = (name || '').trim().replace(/^#+/, '').replace(/[.&]/g, '');
      if (!cleanName) return;
      this.postForm.threads_topic_tag = cleanName;
      this.showThreadsTopicDropdown = false;
      this.showToast(`Đã tạo và áp dụng chủ đề mới: "${cleanName}"`, 'success');
      try {
        await this.authFetch('/api/threads/topics', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: cleanName, category: 'Tùy chỉnh' })
        });
        await this.fetchThreadsTopics();
      } catch (e) {
        console.error('Error saving new Threads topic:', e);
      }
    },

    // ── BULK UPLOAD EXCEL METHODS ──
    async downloadBulkTemplate() {
      try {
        window.open('/api/bulk/template', '_blank');
      } catch (e) {
        this.showToast('Lỗi tải file mẫu: ' + e.message, 'error');
      }
    },

    handleBulkFileDrop(e) {
      this.isDraggingBulk = false;
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        this.parseBulkFile(e.dataTransfer.files[0]);
      }
    },

    handleBulkFileInput(e) {
      if (e.target.files && e.target.files[0]) {
        this.parseBulkFile(e.target.files[0]);
      }
    },

    async parseBulkFile(file) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await this.authFetch('/api/bulk/preview', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.bulkPreviewPosts = data.posts || [];
          this.showToast(`✨ Đã đọc thành công ${data.count} bài viết từ file Excel!`, 'success');
        } else {
          this.showToast(data.detail || 'Lỗi đọc file Excel', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối khi đọc Excel: ' + e.message, 'error');
      }
    },

    async submitBulkImport() {
      if (!this.bulkPreviewPosts || this.bulkPreviewPosts.length === 0) return;
      this.isImportingBulk = true;
      try {
        const res = await this.authFetch('/api/bulk/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ posts: this.bulkPreviewPosts })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast(`✅ Đã nhập thành công ${data.imported_count} bài viết vào lịch đăng!`, 'success');
          this.bulkPreviewPosts = [];
          this.activeTab = 'scheduled';
          this.loadScheduledPosts();
          this.loadCalendarEvents();
        } else {
          this.showToast(data.detail || 'Lỗi nhập bài viết', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi máy chủ khi nhập bài: ' + e.message, 'error');
      } finally {
        this.isImportingBulk = false;
      }
    },

    // ── ROOTS CATALOG METHODS ──
    
    // ── COMBO MULTI-PRODUCT METHODS ──
    toggleSelectComboProduct(product) {
      const pId = product.id || product.MaNoiBo;
      const idx = this.selectedComboProducts.findIndex(p => (p.id || p.MaNoiBo) === pId);
      if (idx > -1) {
        this.selectedComboProducts.splice(idx, 1);
      } else {
        if (this.selectedComboProducts.length >= 10) {
          this.showToast('Bạn chỉ có thể chọn tối đa 10 sản phẩm vào 1 Combo', 'error');
          return;
        }
        this.selectedComboProducts.push(product);
      }
    },

    isComboProductSelected(product) {
      const pId = product.id || product.MaNoiBo;
      return this.selectedComboProducts.some(p => (p.id || p.MaNoiBo) === pId);
    },

    clearSelectedComboProducts() {
      this.selectedComboProducts = [];
    },

    async openComboCampaignModal() {
      if (this.selectedComboProducts.length === 0) return;
      this.comboModal.show = true;
      this.comboModal.isLoading = true;
      this.comboModal.result = null;
      this.comboModal.copiedPromptIdx = null;

      try {
        const res = await this.authFetch('/api/roots/combo-campaign', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            products: this.selectedComboProducts,
            campaign_angle: 'Tối ưu dinh dưỡng hữu cơ kết hợp'
          })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.comboModal.result = data.data;
        } else {
          this.showToast(data.detail || 'Lỗi tạo chiến dịch Combo AI', 'error');
          this.comboModal.show = false;
        }
      } catch (err) {
        this.showToast('Lỗi kết nối khi gọi AI Combo: ' + err.message, 'error');
        this.comboModal.show = false;
      } finally {
        this.comboModal.isLoading = false;
      }
    },

    closeComboCampaignModal() {
      this.comboModal.show = false;
    },

    copyPromptToClipboard(text, idx) {
      navigator.clipboard.writeText(text).then(() => {
        this.comboModal.copiedPromptIdx = idx;
        this.showToast('✨ Đã copy Prompt AI vào Clipboard!', 'success');
        setTimeout(() => {
          if (this.comboModal.copiedPromptIdx === idx) {
            this.comboModal.copiedPromptIdx = null;
          }
        }, 3000);
      });
    },

    applyComboToComposer() {
      if (!this.comboModal.result) return;
      const res = this.comboModal.result;
      this.postForm.fb_caption = res.fb_caption || '';
      this.postForm.ig_caption = res.ig_caption || '';
      this.postForm.google_caption = res.google_caption || '';
      
      // Auto attach images from selected combo products if available
      const comboImgs = this.selectedComboProducts
        .map(p => p.AnhSanPham || p.hinh_anh)
        .filter(Boolean);
      if (comboImgs.length > 0) {
        this.postForm.images = [...comboImgs];
      }

      this.closeComboCampaignModal();
      this.activeTab = 'composer';
      this.showToast(`✨ Đã nạp thành công nội dung Combo ${this.selectedComboProducts.length} sản phẩm sang Trình Tạo Bài!`, 'success');
    },

    async loadRootsCategories() {
      try {
        const res = await this.authFetch('/api/roots/categories');
        const data = await res.json();
        this.rootsCategories = data.categories || {};
      } catch (e) {
        console.error('Error loading roots categories:', e);
      }
    },

    async loadRootsData() {
      this.isLoadingRoots = true;
      try {
        let url = `/api/roots/products?page=${this.rootsPagination.current_page}&page_size=20`;
        if (this.rootsSearchQuery && this.rootsSearchQuery.trim()) {
          url += `&search=${encodeURIComponent(this.rootsSearchQuery.trim())}`;
        }
        if (this.selectedRootsCategory && this.selectedRootsCategory !== 'all') {
          url += `&category=${encodeURIComponent(this.selectedRootsCategory)}`;
        }
        const res = await this.authFetch(url);
        const data = await res.json();
        this.rootsProducts = data.data || data.products || [];
        if (data.pagination) {
          this.rootsPagination = data.pagination;
        }
      } catch (e) {
        this.showToast('Không thể tải sản phẩm từ ROOTS.vn', 'error');
      } finally {
        this.isLoadingRoots = false;
      }
    },

    changeRootsPage(p) {
      if (p < 1 || (this.rootsPagination.total_pages && p > this.rootsPagination.total_pages)) return;
      this.rootsPagination.current_page = p;
      this.loadRootsData();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    getRootsImageUrl(img) {
      if (!img) return 'https://roots.vn/themes/roots/assets/images/no-image.png';
      if (img.startsWith('http://') || img.startsWith('https://')) return img;
      return `https://img.roots.vn/products/${img.split('?')[0]}`;
    },

    formatRootsPrice(val) {
      const num = parseFloat(val || 0);
      if (num <= 0) return 'Liên hệ';
      return num.toLocaleString('vi-VN') + 'đ';
    },

    hasDiscount(p) {
      const gKm = parseFloat(p.GiaSauKm || p.gia || 0);
      const gOld = parseFloat(p.GiaTruocKm || p.gia_goc || 0);
      return gOld > gKm && gKm > 0;
    },

    calcDiscountPercent(p) {
      const gKm = parseFloat(p.GiaSauKm || p.gia || 0);
      const gOld = parseFloat(p.GiaTruocKm || p.gia_goc || 0);
      if (gOld <= gKm || gOld <= 0) return 0;
      return Math.round(((gOld - gKm) / gOld) * 100);
    },

    async quickGenerateRootsPost(product) {
      this.generatingProductId = product.id;
      this.isGenerating1Click = true;
      try {
        const res = await this.authFetch('/api/roots/quick-generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ product: product, aspect_ratio: '4:5' })
        });
        const d = await res.json();
        if (res.ok && d.success) {
          const generated = d.data;
          this.postForm.images = [generated.feed_image];
          this.postForm.fb_caption = generated.fb_caption;
          this.postForm.ig_caption = generated.ig_caption;
          this.postForm.google_caption = generated.google_caption;
          this.postForm.story_image = generated.story_image;
          this.postForm.story_template = generated.story_template;
          this.postForm.story_hook = generated.story_hook;
          this.postForm.story_link = generated.story_link;
          this.postForm.target_story = true;
          this.activeTab = 'composer';
          this.showToast(`✨ Đã tạo xong ảnh Studio 4:5, Story 9:16 & Caption AI cho ${product.TenSanPham || product.ten_san_pham}!`, 'success');
        } else {
          this.showToast(d.detail || 'Lỗi tạo bài tự động', 'error');
        }
      } catch (err) {
        this.showToast('Lỗi kết nối khi tạo bài: ' + err.message, 'error');
      } finally {
        this.isGenerating1Click = false;
        this.generatingProductId = null;
      }
    },

    // ── SUBMIT POST ──
    async submitPost() {
      if (!this.postForm.fb_caption && !this.postForm.ig_caption && !this.postForm.google_caption && !this.postForm.threads_caption && !this.postForm.story_image && !this.postForm.story_hook) {
        this.showToast('Vui lòng nhập nội dung bài viết hoặc chọn ảnh Story.', 'error');
        return;
      }
      this.isSubmitting = true;
      try {
        const res = await this.authFetch('/api/posts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.postForm)
        });
        const data = await res.json();
        if (res.ok && (data.success || data.post)) {
          if (this.currentUserRole === 'staff') {
            this.showToast('✅ Đã gửi bài vào Hàng đợi chờ Admin phê duyệt!', 'success');
          } else if (this.postForm.action === 'now') {
            this.showToast('🚀 Đã xuất bản bài viết thành công!', 'success');
          } else {
            this.showToast('📅 Đã lên lịch đăng bài tự động!', 'success');
          }
          this.loadScheduledPosts();
          this.loadPendingPosts();
          this.loadCalendarEvents();
        } else {
          this.showToast(data.detail || 'Lỗi gửi bài', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi máy chủ khi gửi bài: ' + e.message, 'error');
      } finally {
        this.isSubmitting = false;
      }
    },

    // ── SETTINGS & GOOGLE CONNECT ──
    async loadSettings() {
      try {
        const res = await this.authFetch('/api/settings');
        if (res.ok) {
          const data = await res.json();
          this.settingsForm = { ...this.settingsForm, ...data };
          if (this.settingsForm.fb_page_id && this.settingsForm.masked_token) {
            this.testSettingsConnection();
          }
        }
      } catch (e) {
        console.error('Error loading settings:', e);
      }
    },

    async saveSettings() {
      this.isSaving = true;
      try {
        const res = await this.authFetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.settingsForm)
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast('✅ Đã lưu cài đặt hệ thống thành công!', 'success');
          this.loadSettings();
        } else {
          this.showToast(data.detail || 'Lỗi lưu cài đặt', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi máy chủ: ' + e.message, 'error');
      } finally {
        this.isSaving = false;
      }
    },

    async testSettingsConnection() {
      this.isTesting = true;
      try {
        const res = await this.authFetch('/api/settings/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            fb_page_id: this.settingsForm.fb_page_id,
            fb_page_access_token: this.settingsForm.fb_page_access_token,
            ig_business_account_id: this.settingsForm.ig_business_account_id
          })
        });
        const data = await res.json();
        if (data.facebook) this.metaStatus.facebook = data.facebook;
        if (data.instagram) this.metaStatus.instagram = data.instagram;
        if (data.facebook && data.facebook.connected) {
          this.showToast(`✅ Đã liên kết Fanpage: ${data.facebook.page_name}!`, 'success');
        }
      } catch (e) {
        console.error('Error testing connection:', e);
      } finally {
        this.isTesting = false;
      }
    },

    async connectGoogle() {
      if (!this.settingsForm.google_client_id || !this.settingsForm.google_client_id.trim()) {
        this.showToast('Vui lòng nhập Google OAuth Client ID trước khi kết nối.', 'error');
        return;
      }
      try {
        await this.saveSettings();
        const res = await this.authFetch('/api/google/auth-url');
        const data = await res.json();
        if (res.ok && data.auth_url) {
          window.location.href = data.auth_url;
        } else {
          this.showToast(data.detail || 'Vui lòng nhập Google Client ID & Secret trước.', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối Google: ' + e.message, 'error');
      }
    },

    async syncGoogleProfile() {
      this.isSyncingGoogle = true;
      try {
        if (this.settingsForm.google_client_secret && this.settingsForm.google_client_secret.trim()) {
          await this.saveSettings();
        }
        const res = await this.authFetch('/api/google/sync-profile', { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.success) {
          const d = data.data || {};
          if (d.google_location_name) this.settingsForm.google_location_name = d.google_location_name;
          if (d.google_logo_url) this.settingsForm.google_logo_url = d.google_logo_url;
          if (d.google_rating) this.settingsForm.google_rating = d.google_rating;
          if (d.google_review_count) this.settingsForm.google_review_count = d.google_review_count;
          this.showToast(`✅ Đã đồng bộ Google Maps: ${d.google_rating || '4.9'}⭐ (${d.google_review_count || '150+'} đánh giá)!`, 'success');
        } else {
          let msg = data.detail || 'Không thể đồng bộ hồ sơ Google Maps.';
          if (msg.includes('client secret is invalid') || msg.includes('invalid_client')) {
            msg = 'Client Secret mới chưa được đồng bộ với phiên đăng nhập. Vui lòng bấm nút màu cam "Liên kết lại tài khoản" để kích hoạt!';
          }
          this.showToast('⚠️ ' + msg, 'error');
        }
      } catch (e) {
        this.showToast('Lỗi khi đồng bộ Google: ' + e.message, 'error');
      } finally {
        this.isSyncingGoogle = false;
      }
    },

    async loadThreadsStatus() {
      try {
        const res = await this.authFetch('/api/threads/status');
        if (res.ok) {
          const data = await res.json();
          this.threadsProfile = data;
        }
      } catch (e) {
        console.error('Error loading Threads status:', e);
      }
    },

    async connectThreads() {
      if (!this.settingsForm.threads_app_id || !this.settingsForm.threads_app_id.trim()) {
        this.showToast('Vui lòng nhập Threads App ID trước khi kết nối.', 'error');
        return;
      }
      try {
        await this.saveSettings();
        const appId = encodeURIComponent(this.settingsForm.threads_app_id.trim());
        const res = await this.authFetch(`/api/threads/auth-url?app_id=${appId}`);
        const data = await res.json();
        if (res.ok && data.auth_url) {
          window.location.href = data.auth_url;
        } else {
          this.showToast(data.detail || 'Không thể tạo liên kết OAuth Threads.', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối Threads: ' + e.message, 'error');
      }
    },

    async testThreadsConnection() {
      try {
        const res = await this.authFetch('/api/threads/test-connection', { method: 'POST' });
        const data = await res.json();
        this.threadsProfile = data;
        if (data.connected) {
          this.showToast(`✅ Threads @${data.username || 'roots.vn'} đã kết nối tốt!`, 'success');
        } else {
          this.showToast(`⚠️ Threads: ${data.error || 'Chưa kết nối'}`, 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kiểm tra Threads: ' + e.message, 'error');
      }
    },

    async runSystemMaintenance() {
      try {
        const res = await this.authFetch('/api/maintenance/run', { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast(`✅ Đã sao lưu database (${data.backup}) và dọn ${data.deleted_orphaned_media} ảnh thừa!`, 'success');
        }
      } catch (e) {
        this.showToast('Lỗi bảo trì: ' + e.message, 'error');
      }
    },

    // ── MEDIA, CALENDAR, QUEUE HELPERS ──
    async loadMediaLibrary() {
      try {
        const res = await this.authFetch('/api/media/library');
        const data = await res.json();
        this.mediaLibrary = data.media || [];
      } catch (e) {}
    },
    async loadScheduledPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=scheduled');
        const data = await res.json();
        this.scheduledPosts = data.posts || [];
        this.loadHistoryPosts();
      } catch (e) {}
    },
    async loadHistoryPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=history');
        const data = await res.json();
        this.historyPosts = data.posts || [];
      } catch (e) {}
    },
    async loadPendingPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=pending');
        const data = await res.json();
        this.pendingPosts = data.posts || [];
      } catch (e) {}
    },
    async loadCalendarEvents() {
      try {
        const res = await this.authFetch('/api/calendar/events');
        const data = await res.json();
        this.calendarEvents = data.events || [];
      } catch (e) {}
    },

    getFilteredCalendarEvents() {
      return (this.calendarEvents || []).filter(ev => {
        if (this.calendarFilterPlatform === 'fb' && !ev.target_fb) return false;
        if (this.calendarFilterPlatform === 'ig' && !ev.target_ig) return false;
        if (this.calendarFilterPlatform === 'threads' && !ev.target_threads) return false;
        if (this.calendarFilterPlatform === 'google' && !ev.target_google) return false;
        if (this.calendarFilterPlatform === 'story' && !ev.target_story) return false;

        if (this.calendarFilterStatus === 'scheduled' && ev.status !== 'scheduled') return false;
        if (this.calendarFilterStatus === 'published' && ev.status !== 'success' && ev.status !== 'published') return false;
        if (this.calendarFilterStatus === 'pending' && ev.status !== 'pending') return false;
        if (this.calendarFilterStatus === 'failed' && ev.status !== 'failed' && ev.status !== 'partial_failed') return false;

        return true;
      });
    },

    getCalendarMonthLabel() {
      const monthNames = [
        'Tháng 1', 'Tháng 2', 'Tháng 3', 'Tháng 4', 'Tháng 5', 'Tháng 6',
        'Tháng 7', 'Tháng 8', 'Tháng 9', 'Tháng 10', 'Tháng 11', 'Tháng 12'
      ];
      return `${monthNames[this.calendarCurrentMonth]}, ${this.calendarCurrentYear}`;
    },

    prevCalendarMonth() {
      if (this.calendarCurrentMonth === 0) {
        this.calendarCurrentMonth = 11;
        this.calendarCurrentYear--;
      } else {
        this.calendarCurrentMonth--;
      }
    },

    nextCalendarMonth() {
      if (this.calendarCurrentMonth === 11) {
        this.calendarCurrentMonth = 0;
        this.calendarCurrentYear++;
      } else {
        this.calendarCurrentMonth++;
      }
    },

    todayCalendarMonth() {
      const now = new Date();
      this.calendarCurrentYear = now.getFullYear();
      this.calendarCurrentMonth = now.getMonth();
    },

    getCalendarGridDays() {
      const year = this.calendarCurrentYear;
      const month = this.calendarCurrentMonth;
      
      const firstDay = new Date(year, month, 1);
      const lastDay = new Date(year, month + 1, 0);
      
      let startDayOfWeek = firstDay.getDay() - 1;
      if (startDayOfWeek === -1) startDayOfWeek = 6;
      
      const days = [];
      const prevMonthLastDay = new Date(year, month, 0).getDate();
      
      for (let i = startDayOfWeek - 1; i >= 0; i--) {
        const d = prevMonthLastDay - i;
        const prevMonth = month === 0 ? 11 : month - 1;
        const prevYear = month === 0 ? year - 1 : year;
        const dateStr = `${prevYear}-${String(prevMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        days.push({
          dayNumber: d,
          dateStr: dateStr,
          isCurrentMonth: false,
          isToday: false,
          events: this.getEventsForDate(dateStr)
        });
      }
      
      const today = new Date();
      const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
      
      for (let d = 1; d <= lastDay.getDate(); d++) {
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        days.push({
          dayNumber: d,
          dateStr: dateStr,
          isCurrentMonth: true,
          isToday: dateStr === todayStr,
          events: this.getEventsForDate(dateStr)
        });
      }
      
      const remaining = (7 - (days.length % 7)) % 7;
      for (let d = 1; d <= remaining; d++) {
        const nextMonth = month === 11 ? 0 : month + 1;
        const nextYear = month === 11 ? year + 1 : year;
        const dateStr = `${nextYear}-${String(nextMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        days.push({
          dayNumber: d,
          dateStr: dateStr,
          isCurrentMonth: false,
          isToday: false,
          events: this.getEventsForDate(dateStr)
        });
      }
      
      return days;
    },

    getEventsForDate(dateStr) {
      const filtered = this.getFilteredCalendarEvents();
      return filtered.filter(ev => {
        if (!ev.time) return false;
        return ev.time.startsWith(dateStr);
      });
    },

    formatTimeDisplay(timeStr) {
      if (!timeStr) return '';
      try {
        const d = new Date(timeStr);
        if (isNaN(d.getTime())) return timeStr.slice(11, 16) || timeStr;
        return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
      } catch (e) {
        return timeStr.slice(11, 16) || timeStr;
      }
    },

    formatFullDateDisplay(timeStr) {
      if (!timeStr) return 'Chưa có thời gian';
      try {
        const d = new Date(timeStr);
        if (isNaN(d.getTime())) return timeStr;
        return d.toLocaleString('vi-VN', {
          weekday: 'short',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        });
      } catch (e) {
        return timeStr;
      }
    },

    openCalendarPostModal(post) {
      this.selectedCalendarPost = post;
      this.calendarModalCaptionTab = post.target_fb ? 'fb' : (post.target_ig ? 'ig' : (post.target_threads ? 'threads' : 'google'));
      this.showCalendarModal = true;
    },

    closeCalendarPostModal() {
      this.showCalendarModal = false;
      this.selectedCalendarPost = null;
    },

    getPlatformList(post) {
      const list = [];
      if (post.target_fb) list.push({ name: 'Facebook', short: 'FB', icon: 'fa-brands fa-facebook-f', color: 'bg-blue-600 text-white', badgeBg: 'bg-blue-50 text-blue-700 border-blue-200' });
      if (post.target_ig) list.push({ name: 'Instagram', short: 'IG', icon: 'fa-brands fa-instagram', color: 'bg-gradient-to-tr from-amber-500 via-rose-500 to-purple-600 text-white', badgeBg: 'bg-pink-50 text-pink-700 border-pink-200' });
      if (post.target_threads) list.push({ name: 'Threads', short: 'Threads', icon: 'fa-brands fa-threads', color: 'bg-slate-900 text-white', badgeBg: 'bg-slate-100 text-slate-800 border-slate-300' });
      if (post.target_google) list.push({ name: 'Google Maps', short: 'Google', icon: 'fa-brands fa-google', color: 'bg-emerald-600 text-white', badgeBg: 'bg-emerald-50 text-emerald-700 border-emerald-200' });
      if (post.target_story) list.push({ name: 'Story 9:16', short: 'Story', icon: 'fa-solid fa-mobile-screen-button', color: 'bg-purple-600 text-white', badgeBg: 'bg-purple-50 text-purple-700 border-purple-200' });
      return list;
    },
    async loadTemplatesAndHashtags() {
      try {
        const [hRes, tRes] = await Promise.all([
          this.authFetch('/api/hashtag-groups'),
          this.authFetch('/api/caption-templates')
        ]);
        const hData = await hRes.json();
        const tData = await tRes.json();
        this.hashtagGroups = hData.groups || [];
        this.captionTemplates = tData.templates || [];
      } catch (e) {}
    },
    async approvePendingPost(post, action = 'publish_now') {
      try {
        const res = await this.authFetch(`/api/posts/${post.id}/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: action })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast(data.message || 'Đã duyệt bài thành công!', 'success');
          this.loadPendingPosts();
          this.loadScheduledPosts();
        }
      } catch (e) {}
    },
    async rejectPendingPost(post) {
      const reason = prompt('Nhập lý do từ chối:');
      if (reason === null) return;
      try {
        const res = await this.authFetch(`/api/posts/${post.id}/reject`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: reason })
        });
        if (res.ok) {
          this.showToast('Đã từ chối bài viết', 'info');
          this.loadPendingPosts();
        }
      } catch (e) {}
    },
    async publishNow(id) {
      try {
        const res = await this.authFetch(`/api/posts/${id}/publish-now`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
          const r = data.result || {};
          if (r.status === 'failed') {
            this.showToast('❌ Đăng bài thất bại: ' + (r.error_log || 'Có lỗi xảy ra'), 'error');
          } else if (r.status === 'partial_failed') {
            this.showToast('⚠️ Đăng bài thành công 1 phần. Kiểm tra thẻ bài để xem chi tiết.', 'error');
          } else {
            this.showToast('🚀 Đã xuất bản bài viết thành công!', 'success');
          }
          this.loadScheduledPosts();
          this.loadCalendarEvents();
        } else {
          this.showToast(data.detail || 'Lỗi khi gửi yêu cầu đăng bài', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi máy chủ khi đăng bài: ' + e.message, 'error');
      }
    },
    async duplicatePost(id) {
      try {
        const res = await this.authFetch(`/api/posts/${id}/duplicate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast('✨ Đã nhân bản bài viết thành công!', 'success');
          this.loadScheduledPosts();
        }
      } catch (e) {}
    },
    async deleteScheduledPost(id) {
      if (!confirm('Xóa bài viết này?')) return;
      try {
        const res = await this.authFetch(`/api/posts/${id}`, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa bài viết', 'info');
          this.loadScheduledPosts();
        }
      } catch (e) {}
    },
    insertVariable(tag) {
      if (this.captionTab === 'fb') {
        this.postForm.fb_caption = (this.postForm.fb_caption || '') + ' ' + tag;
      } else if (this.captionTab === 'ig') {
        this.postForm.ig_caption = (this.postForm.ig_caption || '') + ' ' + tag;
      } else if (this.captionTab === 'threads') {
        this.postForm.threads_caption = (this.postForm.threads_caption || '') + ' ' + tag;
      } else {
        this.postForm.google_caption = (this.postForm.google_caption || '') + ' ' + tag;
      }
      this.showToast(`Đã chèn "${tag}" vào ô soạn thảo!`, 'info');
    },
    getFbName() {
      return (this.metaStatus && this.metaStatus.facebook && this.metaStatus.facebook.page_name) || 'ROOTS - Organic Store & Juice Bar';
    },
    getFbPic() {
      return (this.metaStatus && this.metaStatus.facebook && this.metaStatus.facebook.picture) || 'https://roots.vn/themes/roots/assets/images/logo.png';
    },
    getIgUsername() {
      return (this.metaStatus && this.metaStatus.instagram && this.metaStatus.instagram.username) || 'rootsvn.official';
    },
    getIgPic() {
      return (this.metaStatus && this.metaStatus.instagram && this.metaStatus.instagram.profile_picture) || this.getFbPic();
    },
    async loadMetaStatus() {
      try {
        const res = await this.authFetch('/api/meta/status');
        if (res.ok) {
          const data = await res.json();
          if (data.facebook) this.metaStatus.facebook = data.facebook;
          if (data.instagram) this.metaStatus.instagram = data.instagram;
        }
      } catch (e) {}
    },
    getStatusBadgeClass(status) {
      if (status === 'scheduled') return 'bg-amber-100 text-amber-800 border border-amber-200';
      if (status === 'pending' || status === 'pending_approval') return 'bg-purple-100 text-purple-800 border border-purple-200';
      if (status === 'failed') return 'bg-rose-100 text-rose-800 border border-rose-200';
      if (status === 'partial_failed') return 'bg-amber-100 text-amber-800 border border-amber-200';
      return 'bg-emerald-100 text-emerald-800 border border-emerald-200';
    },
    getStatusBadgeText(status) {
      if (status === 'scheduled') return '⏳ Đã lên lịch';
      if (status === 'pending' || status === 'pending_approval') return '⏸️ Chờ duyệt';
      if (status === 'failed') return '❌ Thất bại';
      if (status === 'partial_failed') return '⚠️ Một phần lỗi';
      return '✅ Đã xuất bản';
    },
    handleImgError(e) {
      e.target.onerror = null;
      e.target.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 24 24" fill="none" stroke="%2394a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>';
      e.target.classList.add('opacity-40', 'p-2');
    },
    handleGoogleLogoError(e) {
      e.target.onerror = null;
      e.target.src = 'https://roots.vn/images/favicon-180x180.png';
    },
    copyToClipboard(text) {
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
          this.showToast('Đã sao chép link Cron Keep-Alive vào clipboard!', 'success');
        }).catch(() => {
          this.fallbackCopyText(text);
        });
      } else {
        this.fallbackCopyText(text);
      }
    },
    fallbackCopyText(text) {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-999999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        document.execCommand('copy');
        this.showToast('Đã sao chép link Cron Keep-Alive vào clipboard!', 'success');
      } catch (err) {
        prompt('Sao chép đường link bên dưới:', text);
      }
      document.body.removeChild(textArea);
    }
  }
}).mount('#app');