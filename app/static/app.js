const { createApp } = Vue;

createApp({
  data() {
    return {
      isAuthenticated: false,
      authToken: '',
      loginPassword: '',
      showLoginPassword: false,
      loginError: '',
      isLoggingIn: false,

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

      postForm: {
        target_fb: true,
        target_ig: true,
        target_story: true,
        target_google: false,
        story_template: 'organic',
        story_hook: '',
        story_link: 'https://roots.vn',
        story_image: '',
        images: [],
        fb_caption: '',
        ig_caption: '',
        google_caption: '',
        google_action_type: 'LEARN_MORE',
        google_action_url: '',
        action: 'now',
        scheduled_time: ''
      },
      bulkPreviewPosts: [],
      scheduledPosts: [],
      historyPosts: [],
      
      settingsForm: {
        fb_page_id: '',
        fb_page_access_token: '',
        ig_business_account_id: '',
        imgbb_api_key: '',
        gemini_api_key: '',
        gemini_model: 'gemini-3.5-flash-lite',
        google_client_id: '',
        google_client_secret: '',
        google_connected: false,
        google_location_name: '',
        google_location_id: '',
        has_fb_page_access_token: false,
        has_imgbb_api_key: false,
        has_gemini_api_key: false,
        has_google_client_secret: false,
        app_password: ''
      },

      metaStatus: {
        facebook: { connected: false, page_name: '', page_id: '', picture: '' },
        instagram: { connected: false, username: '', account_id: '', profile_picture: '' }
      },

      metaExchange: {
        app_id: '2039281703363967',
        app_secret: '',
        short_token: ''
      },
      isConvertingToken: false,

      aiModal: {
        show: false,
        isLoading: false,
        userHint: '',
        result: null
      },

      toast: {
        show: false,
        message: '',
        type: 'info'
      },
      errorModal: {
        show: false,
        content: ''
      },

      studioModal: {
        show: false,
        isExporting: false,
        showSafeZone: true,
        activeTemplate: 'organic',
        fabricCanvas: null,
        productImgObj: null,
        safeZoneGroup: null
      },
      studioTemplates: [
        { id: 'organic', name: 'Siêu Thị Hữu Cơ', icon: '🌿' },
        { id: 'juice', name: 'Juice Bar', icon: '🍹' },
        { id: 'sale', name: 'Giờ Vàng Sale', icon: '🔥' },
        { id: 'magazine', name: 'Tạp Chí Ẩm Thực', icon: '✨' },
        { id: 'polaroid', name: 'Chụp Polaroid', icon: '📷' }
      ],

      // ROOTS CATALOG STATE
      rootsProducts: [],
      rootsCategories: {},
      selectedRootsCategory: 'all',
      selectedCreativeRatio: '4:5',
      selectedComboProducts: [],
      comboModal: {
        show: false,
        isLoading: false,
        userHint: '',
        result: null,
        activeCaptionTab: 'fb',
        copiedPromptIdx: null
      },
      rootsSearchQuery: '',
      isFlashSaleOnly: false,
      isLoadingRoots: false,
      isGeneratingPost: false,
      generatingProductId: null,
      rootsPagination: {
        current_page: 1,
        total_pages: 1,
        total_items: 0
      },

      // CONTENT CALENDAR (MIXPOST PATTERN)
      calendarCurrentDate: new Date(),
      calendarEvents: [],
      selectedCalendarPost: null,

      // MEDIA LIBRARY (MIXPOST PATTERN)
      mediaLibrary: [],
      mediaSearch: '',
      selectedMediaTag: 'Tất cả',
      mediaTags: ['Tất cả', 'Trái cây', 'Nước ép', 'Bánh ngọt', 'Chăm sóc', 'Khuyến mãi', 'ROOTS'],
      isLoadingMedia: false,
      selectedMediaFiles: [],
      isBatchDeleting: false,

      // TEMPLATES & HASHTAGS (MIXPOST PATTERN)
      hashtagGroups: [],
      captionTemplates: [],
      newHashtagGroup: { name: '', hashtags: '', category: 'Chung' },
      newTemplate: { name: '', content: '', category: 'Sản phẩm', brand_voice: 'Bán hàng' },
      dynamicVariables: [
        { key: 'product_name', label: 'Tên SP' },
        { key: 'brand', label: 'Brand' },
        { key: 'price', label: 'Giá' },
        { key: 'discount', label: 'Giảm giá' },
        { key: 'origin', label: 'Xuất xứ' },
        { key: 'product_url', label: 'Link SP' },
        { key: 'hotline', label: 'Hotline' }
      ],

      // BACKGROUND JOB PROGRESS (DRAMATIQ / WORKER PATTERN)
      activeJob: {
        id: null,
        status: 'idle',
        progress: 0,
        current_step: '',
        error: '',
        timer: null
      },
      showJobModal: false
    };
  },

  computed: {
    isAllMediaSelected() {
      return this.mediaLibrary.length > 0 && this.selectedMediaFiles.length === this.mediaLibrary.length;
    },
    calendarGridCells() {
      const year = this.calendarCurrentDate.getFullYear();
      const month = this.calendarCurrentDate.getMonth();
      const firstDayOfMonth = new Date(year, month, 1);
      const lastDayOfMonth = new Date(year, month + 1, 0);

      let startingDay = firstDayOfMonth.getDay() - 1;
      if (startingDay < 0) startingDay = 6;

      const totalDays = lastDayOfMonth.getDate();
      const prevMonthLastDay = new Date(year, month, 0).getDate();

      const cells = [];
      const today = new Date();
      const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

      // Previous month padding days
      for (let i = startingDay - 1; i >= 0; i--) {
        const d = prevMonthLastDay - i;
        const prevDate = new Date(year, month - 1, d);
        const dateStr = `${prevDate.getFullYear()}-${String(prevDate.getMonth() + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        cells.push({
          dayNum: d,
          dateStr: dateStr,
          isCurrentMonth: false,
          isToday: dateStr === todayStr,
          events: this.getEventsForDate(dateStr)
        });
      }

      // Current month days
      for (let d = 1; d <= totalDays; d++) {
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        cells.push({
          dayNum: d,
          dateStr: dateStr,
          isCurrentMonth: true,
          isToday: dateStr === todayStr,
          events: this.getEventsForDate(dateStr)
        });
      }

      // Next month padding days
      const remaining = (7 - (cells.length % 7)) % 7;
      for (let d = 1; d <= remaining; d++) {
        const nextDate = new Date(year, month + 1, d);
        const dateStr = `${nextDate.getFullYear()}-${String(nextDate.getMonth() + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        cells.push({
          dayNum: d,
          dateStr: dateStr,
          isCurrentMonth: false,
          isToday: dateStr === todayStr,
          events: this.getEventsForDate(dateStr)
        });
      }
      return cells;
    }
  },

  async mounted() {
    await this.checkAuth();
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);
    this.postForm.scheduled_time = tomorrow.toISOString().slice(0, 16);
  },

  methods: {
    // ── AUTH METHODS ──
    async authFetch(url, options = {}) {
      if (!options.headers) options.headers = {};
      options.credentials = 'same-origin';
      const res = await fetch(url, options);
      if (res.status === 401) {
        this.isAuthenticated = false;
        this.authToken = '';
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
            this.loadSettings();
            this.loadScheduledPosts();
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
          this.loginPassword = '';
          this.showToast('Đăng nhập thành công!', 'success');
          this.loadSettings();
          this.loadScheduledPosts();
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
        this.authToken = '';
        this.showToast('Đã đăng xuất', 'info');
      }
    },
    showToast(message, type = 'info') {
      this.toast.message = message;
      this.toast.type = type;
      this.toast.show = true;
      setTimeout(() => {
        this.toast.show = false;
      }, 4000);
    },

    // ── CALENDAR METHODS ──
    formatCalendarMonthHeader(date) {
      if (!date) return '';
      const months = ['Tháng 1', 'Tháng 2', 'Tháng 3', 'Tháng 4', 'Tháng 5', 'Tháng 6', 'Tháng 7', 'Tháng 8', 'Tháng 9', 'Tháng 10', 'Tháng 11', 'Tháng 12'];
      return `${months[date.getMonth()]} năm ${date.getFullYear()}`;
    },
    changeCalendarMonth(offset) {
      const current = new Date(this.calendarCurrentDate);
      current.setMonth(current.getMonth() + offset);
      this.calendarCurrentDate = current;
      this.loadCalendarEvents();
    },
    async loadCalendarEvents() {
      try {
        const res = await this.authFetch('/api/calendar/events');
        const data = await res.json();
        if (res.ok) {
          this.calendarEvents = data.events || [];
        }
      } catch (err) {
        console.error('Error loading calendar events:', err);
      }
    },
    getEventsForDate(dateStr) {
      return this.calendarEvents.filter(ev => {
        if (!ev.time) return false;
        return ev.time.startsWith(dateStr);
      });
    },
    openCalendarEventModal(ev) {
      if (confirm(`Bạn có muốn nhân bản bài viết "${ev.title}" sang thời gian mới?`)) {
        this.duplicatePost(ev.id);
      }
    },
    async duplicatePost(postId) {
      try {
        const res = await this.authFetch(`/api/posts/${postId}/duplicate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const data = await res.json();
        if (res.ok) {
          this.showToast('✅ Đã nhân bản bài viết thành công!', 'success');
          this.loadCalendarEvents();
          this.loadScheduledPosts();
        } else {
          this.showToast(data.detail || 'Lỗi nhân bản bài viết', 'error');
        }
      } catch (err) {
        this.showToast('Lỗi kết nối khi nhân bản', 'error');
      }
    },

    // ── MEDIA LIBRARY METHODS ──
    async loadMediaLibrary() {
      this.isLoadingMedia = true;
      try {
        const params = new URLSearchParams();
        if (this.mediaSearch) params.append('search', this.mediaSearch);
        if (this.selectedMediaTag && this.selectedMediaTag !== 'Tất cả') params.append('tag', this.selectedMediaTag);
        const res = await this.authFetch(`/api/media/library?${params.toString()}`);
        const data = await res.json();
        if (res.ok) {
          this.mediaLibrary = data.media || [];
        }
      } catch (err) {
        console.error('Error loading media library:', err);
      } finally {
        this.isLoadingMedia = false;
      }
    },
    triggerMediaLibUpload() {
      if (this.$refs.mediaLibFileInput) this.$refs.mediaLibFileInput.click();
    },
    async handleMediaLibUpload(event) {
      const files = event.target.files;
      if (!files || files.length === 0) return;
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
      }
      try {
        const res = await this.authFetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (res.ok) {
          this.showToast('✅ Đã tải ảnh lên thư viện thành công!', 'success');
          this.loadMediaLibrary();
        } else {
          this.showToast(data.detail || 'Lỗi tải ảnh', 'error');
        }
      } catch (err) {
        this.showToast('Lỗi mạng khi tải ảnh', 'error');
      } finally {
        event.target.value = '';
      }
    },
    selectMediaForPost(filename) {
      if (!this.postForm.images.includes(filename)) {
        this.postForm.images.push(filename);
      }
      this.activeTab = 'composer';
      this.showToast('✅ Đã thêm ảnh vào bài soạn!', 'success');
    },
    toggleSelectMedia(filename) {
      const idx = this.selectedMediaFiles.indexOf(filename);
      if (idx > -1) {
        this.selectedMediaFiles.splice(idx, 1);
      } else {
        this.selectedMediaFiles.push(filename);
      }
    },
    toggleSelectAllMedia() {
      if (this.isAllMediaSelected) {
        this.selectedMediaFiles = [];
      } else {
        this.selectedMediaFiles = this.mediaLibrary.map(m => m.filename);
      }
    },
    clearSelectedMedia() {
      this.selectedMediaFiles = [];
    },
    async deleteSelectedMediaBatch() {
      if (this.selectedMediaFiles.length === 0) return;
      const count = this.selectedMediaFiles.length;
      if (!confirm(`Bạn có chắc chắn muốn xóa ${count} ảnh đã chọn khỏi Thư viện?`)) return;
      this.isBatchDeleting = true;
      try {
        const res = await this.authFetch('/api/media/batch-delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filenames: this.selectedMediaFiles })
        });
        const data = await res.json();
        if (res.ok) {
          this.showToast(`✅ Đã xóa thành công ${data.deleted_count || count} ảnh!`, 'success');
          this.selectedMediaFiles = [];
          this.loadMediaLibrary();
        } else {
          this.showToast(data.detail || 'Lỗi xóa nhiều ảnh', 'error');
        }
      } catch (err) {
        this.showToast('Lỗi mạng khi xóa ảnh', 'error');
      } finally {
        this.isBatchDeleting = false;
      }
    },
    async deleteMediaLibraryFile(filename) {
      if (!confirm('Bạn có chắc chắn muốn xóa ảnh này khỏi thư viện?')) return;
      try {
        const res = await this.authFetch(`/api/media/${filename}`, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa ảnh', 'info');
          this.loadMediaLibrary();
        }
      } catch (err) {
        this.showToast('Lỗi xóa ảnh', 'error');
      }
    },

    // ── TEMPLATES & HASHTAGS METHODS ──
    async loadTemplatesAndHashtags() {
      try {
        const [rHt, rTpl] = await Promise.all([
          this.authFetch('/api/hashtag-groups'),
          this.authFetch('/api/caption-templates')
        ]);
        const dHt = await rHt.json();
        const dTpl = await rTpl.json();
        if (rHt.ok) this.hashtagGroups = dHt.groups || [];
        if (rTpl.ok) this.captionTemplates = dTpl.templates || [];
      } catch (err) {
        console.error('Error loading templates:', err);
      }
    },
    insertVariable(tag) {
      if (this.captionTab === 'fb') {
        this.postForm.fb_caption = (this.postForm.fb_caption || '') + ' ' + tag;
      } else if (this.captionTab === 'ig') {
        this.postForm.ig_caption = (this.postForm.ig_caption || '') + ' ' + tag;
      } else {
        this.postForm.google_caption = (this.postForm.google_caption || '') + ' ' + tag;
      }
    },
    insertHashtagGroup(hashtags) {
      if (!hashtags) return;
      if (this.captionTab === 'fb') {
        this.postForm.fb_caption = (this.postForm.fb_caption || '') + '\n\n' + hashtags;
      } else if (this.captionTab === 'ig') {
        this.postForm.ig_caption = (this.postForm.ig_caption || '') + '\n\n' + hashtags;
      } else {
        this.postForm.google_caption = (this.postForm.google_caption || '') + '\n\n' + hashtags;
      }
      this.showToast('✅ Đã chèn nhóm hashtag', 'success');
    },
    applyCaptionTemplate(content) {
      if (!content) return;
      if (this.captionTab === 'fb') {
        this.postForm.fb_caption = content;
      } else if (this.captionTab === 'ig') {
        this.postForm.ig_caption = content;
      } else {
        this.postForm.google_caption = content;
      }
      this.showToast('✅ Đã áp dụng mẫu nội dung', 'success');
    },
    async saveNewHashtagGroup() {
      try {
        const res = await this.authFetch('/api/hashtag-groups', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.newHashtagGroup)
        });
        if (res.ok) {
          this.showToast('✅ Đã lưu nhóm hashtag mới!', 'success');
          this.newHashtagGroup = { name: '', hashtags: '', category: 'Chung' };
          this.loadTemplatesAndHashtags();
        }
      } catch (err) {
        this.showToast('Lỗi lưu nhóm hashtag', 'error');
      }
    },
    async deleteHashtagGroupItem(id) {
      if (!confirm('Xóa nhóm hashtag này?')) return;
      try {
        const res = await this.authFetch(`/api/hashtag-groups/${id}`, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa nhóm hashtag', 'info');
          this.loadTemplatesAndHashtags();
        }
      } catch (err) {}
    },
    async saveNewCaptionTemplate() {
      try {
        const res = await this.authFetch('/api/caption-templates', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.newTemplate)
        });
        if (res.ok) {
          this.showToast('✅ Đã lưu mẫu nội dung mới!', 'success');
          this.newTemplate = { name: '', content: '', category: 'Sản phẩm', brand_voice: 'Bán hàng' };
          this.loadTemplatesAndHashtags();
        }
      } catch (err) {
        this.showToast('Lỗi lưu mẫu nội dung', 'error');
      }
    },
    async deleteCaptionTemplateItem(id) {
      if (!confirm('Xóa mẫu nội dung này?')) return;
      try {
        const res = await this.authFetch('/api/caption-templates/' + id, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa mẫu nội dung', 'info');
          this.loadTemplatesAndHashtags();
        }
      } catch (err) {}
    },

    // ── BACKGROUND JOB PROGRESS (DRAMATIQ / WORKER PATTERN) ──
    async generatePostFromProduct(p) {
      if (this.isGeneratingPost) return;
      this.activeJob.id = null;
      this.activeJob.status = 'processing';
      this.activeJob.progress = 10;
      this.activeJob.current_step = 'Đang gửi yêu cầu khởi tạo tác vụ...';
      this.activeJob.error = '';
      this.showJobModal = true;
      this.isGeneratingPost = true;
      this.generatingProductId = p.id || p.MaNoiBo;

      try {
        const res = await this.authFetch('/api/roots/start-quick-generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            product: p,
            aspect_ratio: this.selectedCreativeRatio || '4:5'
          })
        });
        const data = await res.json();
        if (res.ok && data.job_id) {
          this.activeJob.id = data.job_id;
          this.pollJobProgress(data.job_id);
        } else {
          throw new Error(data.detail || 'Không thể khởi tạo tác vụ nền');
        }
      } catch (err) {
        this.activeJob.status = 'failed';
        this.activeJob.error = err.message;
        this.isGeneratingPost = false;
        this.generatingProductId = null;
      }
    },
    async pollJobProgress(jobId) {
      if (this.activeJob.timer) clearInterval(this.activeJob.timer);
      this.activeJob.timer = setInterval(async () => {
        try {
          const res = await this.authFetch(`/api/jobs/${jobId}`);
          const data = await res.json();
          if (res.ok) {
            this.activeJob.progress = data.progress || 0;
            this.activeJob.current_step = data.current_step || '';
            this.activeJob.status = data.status;

            if (data.status === 'completed') {
              clearInterval(this.activeJob.timer);
              const d = data.result || {};
              this.postForm.images = [d.feed_image || d.square_image];
              this.postForm.fb_caption = d.fb_caption;
              this.postForm.ig_caption = d.ig_caption;
              this.postForm.google_caption = d.google_caption;
              this.postForm.story_hook = d.story_hook;
              this.postForm.story_link = d.product_url;
              this.postForm.story_image = d.story_image;
              this.postForm.story_template = d.story_template || 'organic';
              this.postForm.target_fb = true;
              this.postForm.target_ig = true;
              this.postForm.target_story = true;
              this.postForm.target_google = Boolean(this.settingsForm.google_connected && this.settingsForm.google_location_id);
              this.postForm.google_action_type = 'ORDER';
              this.postForm.google_action_url = d.product_url;

              this.isGeneratingPost = false;
              this.generatingProductId = null;
              setTimeout(() => {
                this.showJobModal = false;
                this.activeTab = 'composer';
                this.showToast('🎉 Đã tạo social creative 4:5 và Story hoàn chỉnh!', 'success');
              }, 800);
            } else if (data.status === 'failed' || data.status === 'cancelled') {
              clearInterval(this.activeJob.timer);
              this.activeJob.error = data.error_message || 'Tác vụ đã bị hủy hoặc gặp lỗi.';
              this.isGeneratingPost = false;
              this.generatingProductId = null;
            }
          }
        } catch (e) {
          console.error('Job polling error:', e);
        }
      }, 600);
    },
    async cancelActiveJob() {
      if (!this.activeJob.id) return;
      try {
        await this.authFetch(`/api/jobs/${this.activeJob.id}/cancel`, { method: 'POST' });
        this.activeJob.status = 'cancelled';
        this.activeJob.current_step = 'Đã hủy tác vụ';
        this.showToast('Đã hủy tác vụ nền', 'info');
      } catch (e) {}
      this.isGeneratingPost = false;
      this.generatingProductId = null;
    },

    // ── MEDIA UPLOAD & COMPOSER METHODS ──
    triggerFileInput() {
      this.$refs.fileInput.click();
    },
    async handleFileSelect(e) {
      const files = e.target.files;
      if (files.length > 0) {
        await this.uploadFiles(files);
      }
      e.target.value = '';
    },
    async handleDrop(e) {
      this.isDragging = false;
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        await this.uploadFiles(files);
      }
    },
    async uploadFiles(files) {
      if (this.postForm.images.length + files.length > 10) {
        this.showToast('Chỉ được chọn tối đa 10 hình ảnh cho mỗi bài đăng.', 'warning');
        return;
      }
      const formData = new FormData();
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
      }
      try {
        const res = await this.authFetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        const filenames = data.filenames || (data.uploaded ? data.uploaded.map(u => u.filename) : []);
        if (res.ok && filenames.length > 0) {
          this.postForm.images.push(...filenames);
          this.showToast(`Đã tải lên ${filenames.length} ảnh!`, 'success');
        } else {
          this.showToast(data.detail || 'Lỗi tải ảnh lên', 'error');
        }
      } catch (err) {
        this.showToast('Lỗi mạng khi tải ảnh', 'error');
      }
    },
    removeImage(index) {
      this.postForm.images.splice(index, 1);
    },
    getMediaUrl(img) {
      if (!img) return '';
      if (img.startsWith('http://') || img.startsWith('https://')) return img;
      return `/api/media/${img}`;
    },
    formatDate(dateStr) {
      if (!dateStr) return '';
      const d = new Date(dateStr);
      return d.toLocaleString('vi-VN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
      });
    },

    // ── STORY STUDIO & FABRIC.JS METHODS ──
    async generateStoryPreview() {
      if (this.postForm.images.length === 0) {
        this.showToast('Vui lòng tải lên ít nhất 1 ảnh trước khi tạo Story.', 'warning');
        return;
      }
      this.isGeneratingStory = true;
      try {
        const res = await this.authFetch('/api/story/preview-generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image_name: this.postForm.images[0],
            hook: this.postForm.story_hook,
            caption: this.postForm.fb_caption || this.postForm.ig_caption,
            template: this.postForm.story_template,
            link: this.postForm.story_link
          })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.postForm.story_image = data.story_image;
          this.showToast('Đã tạo ảnh Story 9:16 mới!', 'success');
        } else {
          throw new Error(data.detail || 'Lỗi tạo Story');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.isGeneratingStory = false;
      }
    },
    async generateAiHook() {
      if (!this.postForm.fb_caption && !this.postForm.ig_caption) {
        this.showToast('Vui lòng nhập nội dung bài viết trước để AI gợi ý Hook.', 'warning');
        return;
      }
      this.isGeneratingAiHook = true;
      try {
        const res = await this.authFetch('/api/ai/generate-caption', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            images: this.postForm.images,
            user_hint: (this.postForm.fb_caption || this.postForm.ig_caption) + '\n\nHãy tạo 1 câu Hook ngắn giật tít dưới 15 từ cho Story 9:16.'
          })
        });
        const data = await res.json();
        if (res.ok && data.captions) {
          const raw = data.captions.trend_caption || data.captions.sales_caption || '';
          this.postForm.story_hook = raw.split('\n')[0].replace('"', '').replace('"', '').trim();
          this.showToast('Đã tạo câu Hook Story từ AI!', 'success');
        }
      } catch (err) {
        this.showToast('Lỗi gợi ý Hook: ' + err.message, 'error');
      } finally {
        this.isGeneratingAiHook = false;
      }
    },
    openStoryStudio() {
      if (this.postForm.images.length === 0) {
        this.showToast('Vui lòng tải lên ít nhất 1 ảnh để mở Story Studio.', 'warning');
        return;
      }
      this.studioModal.activeTemplate = this.postForm.story_template || 'organic';
      this.studioModal.show = true;
      this.$nextTick(() => {
        this.initFabricCanvas();
      });
    },
    closeStoryStudio() {
      this.studioModal.show = false;
      if (this.studioModal.fabricCanvas) {
        this.studioModal.fabricCanvas.dispose();
        this.studioModal.fabricCanvas = null;
      }
    },
    initFabricCanvas() {
      const W = 360;
      const H = 640;
      const canvasEl = document.getElementById('studio-fabric-canvas');
      if (!canvasEl) return;
      if (this.studioModal.fabricCanvas) {
        this.studioModal.fabricCanvas.dispose();
      }
      const canvas = new fabric.Canvas('studio-fabric-canvas', {
        width: W,
        height: H,
        backgroundColor: '#1e293b',
        preserveObjectStacking: true
      });
      this.studioModal.fabricCanvas = canvas;
      this.applyStudioTemplate(this.studioModal.activeTemplate);
    },
    applyStudioTemplate(templateId) {
      this.studioModal.activeTemplate = templateId;
      const canvas = this.studioModal.fabricCanvas;
      if (!canvas) return;
      canvas.clear();
      
      const W = canvas.width;
      const H = canvas.height;

      let bgGradient;
      if (templateId === 'organic') {
        bgGradient = new fabric.Gradient({
          type: 'linear',
          gradientUnits: 'pixels',
          coords: { x1: 0, y1: 0, x2: 0, y2: H },
          colorStops: [
            { offset: 0, color: '#064e3b' },
            { offset: 0.5, color: '#047857' },
            { offset: 1, color: '#022c22' }
          ]
        });
      } else if (templateId === 'juice') {
        bgGradient = new fabric.Gradient({
          type: 'linear',
          gradientUnits: 'pixels',
          coords: { x1: 0, y1: 0, x2: 0, y2: H },
          colorStops: [
            { offset: 0, color: '#7c2d12' },
            { offset: 0.5, color: '#ea580c' },
            { offset: 1, color: '#451a03' }
          ]
        });
      } else if (templateId === 'sale') {
        bgGradient = new fabric.Gradient({
          type: 'linear',
          gradientUnits: 'pixels',
          coords: { x1: 0, y1: 0, x2: 0, y2: H },
          colorStops: [
            { offset: 0, color: '#881337' },
            { offset: 0.5, color: '#e11d48' },
            { offset: 1, color: '#4c0519' }
          ]
        });
      } else if (templateId === 'magazine') {
        bgGradient = new fabric.Gradient({
          type: 'linear',
          gradientUnits: 'pixels',
          coords: { x1: 0, y1: 0, x2: 0, y2: H },
          colorStops: [
            { offset: 0, color: '#0f172a' },
            { offset: 0.5, color: '#1e293b' },
            { offset: 1, color: '#020617' }
          ]
        });
      } else {
        bgGradient = new fabric.Gradient({
          type: 'linear',
          gradientUnits: 'pixels',
          coords: { x1: 0, y1: 0, x2: 0, y2: H },
          colorStops: [
            { offset: 0, color: '#312e81' },
            { offset: 0.5, color: '#4338ca' },
            { offset: 1, color: '#1e1b4b' }
          ]
        });
      }
      canvas.setBackgroundColor(bgGradient, canvas.renderAll.bind(canvas));

      if (this.postForm.images.length > 0) {
        const imgUrl = this.getMediaUrl(this.postForm.images[0]);
        fabric.Image.fromURL(imgUrl, (img) => {
          if (!img) return;
          const maxW = W * 0.75;
          const maxH = H * 0.45;
          const scale = Math.min(maxW / img.width, maxH / img.height);
          img.set({
            scaleX: scale,
            scaleY: scale,
            left: W / 2,
            top: H * 0.45,
            originX: 'center',
            originY: 'center',
            shadow: new fabric.Shadow({
              color: 'rgba(0,0,0,0.4)',
              blur: 15,
              offsetX: 0,
              offsetY: 8
            })
          });
          this.studioModal.productImgObj = img;
          canvas.add(img);
          canvas.renderAll();
        }, { crossOrigin: 'anonymous' });
      }

      const headlineText = this.postForm.story_hook || 'ƯU ĐÃI ĐẶC BIỆT';
      const headline = new fabric.IText(headlineText, {
        left: W / 2,
        top: 80,
        originX: 'center',
        originY: 'top',
        fontSize: 20,
        fontWeight: '900',
        fill: '#ffffff',
        textAlign: 'center',
        shadow: new fabric.Shadow({ color: 'rgba(0,0,0,0.6)', blur: 8, offsetY: 2 })
      });
      canvas.add(headline);

      const ctaBg = new fabric.Rect({
        width: 180,
        height: 38,
        rx: 19,
        ry: 19,
        fill: '#ffffff',
        shadow: new fabric.Shadow({ color: 'rgba(0,0,0,0.3)', blur: 10, offsetY: 4 })
      });
      const ctaLabel = new fabric.Text('XEM CHI TIẾT ↗', {
        fontSize: 12,
        fontWeight: 'bold',
        fill: '#0f172a',
        originX: 'center',
        originY: 'center'
      });
      const ctaGroup = new fabric.Group([ctaBg, ctaLabel], {
        left: W / 2,
        top: H - 100,
        originX: 'center',
        originY: 'center',
        selectable: true
      });
      canvas.add(ctaGroup);

      this.updateSafeZoneOverlay();
      canvas.renderAll();
    },
    updateSafeZoneOverlay() {
      const canvas = this.studioModal.fabricCanvas;
      if (!canvas) return;
      if (this.studioModal.safeZoneGroup) {
        canvas.remove(this.studioModal.safeZoneGroup);
        this.studioModal.safeZoneGroup = null;
      }
      if (!this.studioModal.showSafeZone) {
        canvas.renderAll();
        return;
      }
      const W = canvas.width;
      const H = canvas.height;
      const topH = 65;
      const botH = 80;

      const topZone = new fabric.Rect({
        left: 0, top: 0, width: W, height: topH,
        fill: 'rgba(239, 68, 68, 0.2)',
        selectable: false, evented: false
      });
      const topText = new fabric.Text('⚠️ Vùng Avt / Header (Không che)', {
        left: W / 2, top: topH / 2, originX: 'center', originY: 'center',
        fontSize: 10, fill: '#fca5a5', fontWeight: 'bold', selectable: false, evented: false
      });
      const botZone = new fabric.Rect({
        left: 0, top: H - botH, width: W, height: botH,
        fill: 'rgba(239, 68, 68, 0.2)',
        selectable: false, evented: false
      });
      const botText = new fabric.Text('⚠️ Vùng Nhắn tin / Swipe Up', {
        left: W / 2, top: H - (botH / 2), originX: 'center', originY: 'center',
        fontSize: 10, fill: '#fca5a5', fontWeight: 'bold', selectable: false, evented: false
      });

      const group = new fabric.Group([topZone, topText, botZone, botText], {
        selectable: false, evented: false
      });
      this.studioModal.safeZoneGroup = group;
      canvas.add(group);
      canvas.renderAll();
    },
    toggleSafeZone() {
      this.studioModal.showSafeZone = !this.studioModal.showSafeZone;
      this.updateSafeZoneOverlay();
    },
    addStudioText() {
      const canvas = this.studioModal.fabricCanvas;
      if (!canvas) return;
      const text = new fabric.IText('Nhấp đúp để sửa chữ', {
        left: canvas.width / 2,
        top: 200,
        originX: 'center',
        fontSize: 16,
        fill: '#fde047',
        fontWeight: 'bold',
        shadow: new fabric.Shadow({ color: 'rgba(0,0,0,0.5)', blur: 6, offsetY: 2 })
      });
      canvas.add(text);
      canvas.setActiveObject(text);
      canvas.renderAll();
    },
    addStudioSticker(emoji) {
      const canvas = this.studioModal.fabricCanvas;
      if (!canvas) return;
      const sticker = new fabric.Text(emoji, {
        left: canvas.width / 2,
        top: canvas.height / 2,
        originX: 'center',
        originY: 'center',
        fontSize: 48,
        shadow: new fabric.Shadow({ color: 'rgba(0,0,0,0.3)', blur: 8, offsetY: 4 })
      });
      canvas.add(sticker);
      canvas.setActiveObject(sticker);
      canvas.renderAll();
    },
    deleteSelectedStudioObject() {
      const canvas = this.studioModal.fabricCanvas;
      if (!canvas) return;
      const activeObj = canvas.getActiveObject();
      if (activeObj && activeObj !== this.studioModal.safeZoneGroup) {
        canvas.remove(activeObj);
        canvas.discardActiveObject();
        canvas.renderAll();
      }
    },
    async exportAndApplyStory() {
      const canvas = this.studioModal.fabricCanvas;
      if (!canvas) return;
      this.studioModal.isExporting = true;
      if (this.studioModal.safeZoneGroup) {
        canvas.remove(this.studioModal.safeZoneGroup);
        this.studioModal.safeZoneGroup = null;
      }
      canvas.renderAll();

      const dataUrl = canvas.toDataURL({
        format: 'jpeg',
        quality: 0.95,
        multiplier: 3
      });

      try {
        const blob = await (await fetch(dataUrl)).blob();
        const file = new File([blob], `studio_story_${Date.now()}.jpg`, { type: 'image/jpeg' });
        const formData = new FormData();
        formData.append('files', file);

        const res = await this.authFetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (res.ok && data.filenames && data.filenames.length > 0) {
          this.postForm.story_image = data.filenames[0];
          this.postForm.target_story = true;
          this.showToast('✅ Đã xuất Story từ Studio thành công!', 'success');
          this.closeStoryStudio();
        } else {
          throw new Error('Không thể lưu ảnh Story đã xuất');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.studioModal.isExporting = false;
      }
    },

    // ── BULK UPLOAD METHODS ──
    async downloadTemplate() {
      try {
        const res = await fetch('/api/bulk/template');
        if (!res.ok) throw new Error('Không thể tải file mẫu');
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'sample_bulk_posts.xlsx';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        this.showToast('Đã tải xuống file Excel mẫu (.xlsx)!', 'success');
      } catch (e) {
        this.showToast('Lỗi tải file mẫu: ' + e.message, 'error');
      }
    },
    handleBulkFileSelect(e) {
      const file = e.target.files[0];
      if (file) this.processBulkFile(file);
      e.target.value = '';
    },
    handleBulkDrop(e) {
      this.isDraggingBulk = false;
      const file = e.dataTransfer.files[0];
      if (file) this.processBulkFile(file);
    },
    async processBulkFile(file) {
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
          this.showToast(`Đã đọc ${this.bulkPreviewPosts.length} bài viết từ file!`, 'success');
        } else {
          throw new Error(data.detail || 'Lỗi đọc file Excel/CSV');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      }
    },
    async submitBulkImport() {
      if (this.bulkPreviewPosts.length === 0) return;
      this.isImportingBulk = true;
      try {
        const res = await this.authFetch('/api/bulk/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ posts: this.bulkPreviewPosts })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast(`Đã nhập ${data.count} bài viết vào hàng đợi!`, 'success');
          this.bulkPreviewPosts = [];
          this.activeTab = 'scheduled';
          this.loadScheduledPosts();
          this.loadCalendarEvents();
        } else {
          throw new Error(data.detail || 'Lỗi nhập danh sách bài viết');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.isImportingBulk = false;
      }
    },

    // ── POST SUBMIT & MANAGEMENT METHODS ──
    async submitPost() {
      if (!this.postForm.target_fb && !this.postForm.target_ig && !this.postForm.target_story && !this.postForm.target_google) {
        this.showToast('Vui lòng chọn ít nhất 1 nền tảng đăng (FB, IG, Story hoặc Google Business).', 'warning');
        return;
      }
      if (this.postForm.target_fb && !this.postForm.fb_caption && this.postForm.images.length === 0) {
        this.showToast('Facebook yêu cầu nội dung caption hoặc ít nhất 1 ảnh.', 'warning');
        return;
      }
      if (this.postForm.target_ig && this.postForm.images.length === 0) {
        this.showToast('Instagram yêu cầu ít nhất 1 hình ảnh để đăng.', 'warning');
        return;
      }
      if (this.postForm.target_story && !this.postForm.story_image && this.postForm.images.length === 0) {
        this.showToast('Story yêu cầu ít nhất 1 ảnh để đăng.', 'warning');
        return;
      }
      if (this.postForm.target_google && !this.postForm.google_caption && !this.postForm.fb_caption) {
        this.showToast('Google Business Profile yêu cầu nội dung bài viết.', 'warning');
        return;
      }
      if (this.postForm.action === 'schedule' && !this.postForm.scheduled_time) {
        this.showToast('Vui lòng chọn thời gian lên lịch đăng bài.', 'warning');
        return;
      }

      this.isSubmitting = true;
      try {
        const payload = {
          fb_caption: this.postForm.fb_caption,
          ig_caption: this.postForm.ig_caption,
          google_caption: this.postForm.google_caption,
          images: this.postForm.images,
          target_fb: this.postForm.target_fb,
          target_ig: this.postForm.target_ig,
          target_story: this.postForm.target_story,
          target_google: this.postForm.target_google,
          google_action_type: this.postForm.google_action_type,
          google_action_url: this.postForm.google_action_url,
          story_image: this.postForm.story_image,
          story_template: this.postForm.story_template,
          story_hook: this.postForm.story_hook,
          story_link: this.postForm.story_link,
          scheduled_time: this.postForm.action === 'schedule' ? this.postForm.scheduled_time : null
        };

        const res = await this.authFetch('/api/posts/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && data.success) {
          if (this.postForm.action === 'now') {
            this.showToast('🎉 Đã đăng bài thành công lên các nền tảng!', 'success');
            this.activeTab = 'history';
            this.loadHistoryPosts();
          } else {
            this.showToast('⏰ Đã lên lịch đăng bài thành công!', 'success');
            this.activeTab = 'scheduled';
            this.loadScheduledPosts();
          }
          this.loadCalendarEvents();
          // Reset postForm
          this.postForm.images = [];
          this.postForm.fb_caption = '';
          this.postForm.ig_caption = '';
          this.postForm.google_caption = '';
          this.postForm.story_hook = '';
          this.postForm.story_image = '';
        } else {
          throw new Error(data.detail || 'Lỗi xử lý bài viết');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.isSubmitting = false;
      }
    },
    async loadScheduledPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=scheduled');
        const data = await res.json();
        if (res.ok) {
          this.scheduledPosts = data.posts || [];
        }
      } catch (e) {}
    },
    async loadHistoryPosts() {
      try {
        const res = await this.authFetch('/api/posts?filter_type=history');
        const data = await res.json();
        if (res.ok) {
          this.historyPosts = data.posts || [];
        }
      } catch (e) {}
    },
    async publishPostNow(postId) {
      try {
        const res = await this.authFetch(`/api/posts/${postId}/publish-now`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
          this.showToast('Đang tiến hành đăng bài...', 'info');
          this.loadScheduledPosts();
          this.loadHistoryPosts();
          this.loadCalendarEvents();
        } else {
          this.showToast(data.detail || 'Lỗi đăng bài ngay', 'error');
        }
      } catch (e) {
        this.showToast('Lỗi kết nối', 'error');
      }
    },
    async deletePost(postId) {
      if (!confirm('Bạn có chắc muốn xóa bài viết này?')) return;
      try {
        const res = await this.authFetch(`/api/posts/${postId}`, { method: 'DELETE' });
        if (res.ok) {
          this.showToast('Đã xóa bài viết', 'info');
          this.loadScheduledPosts();
          this.loadHistoryPosts();
          this.loadCalendarEvents();
        }
      } catch (e) {}
    },
    showErrorDetails(log) {
      this.errorModal.content = log;
      this.errorModal.show = true;
    },

    // ── SETTINGS & INTEGRATIONS METHODS ──
    async loadSettings() {
      try {
        const res = await this.authFetch('/api/settings');
        const data = await res.json();
        if (res.ok) {
          const s = data.settings || data;
          this.settingsForm.fb_page_id = s.fb_page_id || '';
          this.settingsForm.ig_business_account_id = s.ig_business_account_id || '';
          this.settingsForm.google_client_id = s.google_client_id || '';
          this.settingsForm.gemini_model = s.gemini_model || 'gemini-3.5-flash-lite';
          this.settingsForm.google_connected = Boolean(s.google_connected);
          this.settingsForm.google_location_name = s.google_location_name || '';
          this.settingsForm.google_location_id = s.google_location_id || '';
          this.settingsForm.has_fb_page_access_token = Boolean(s.masked_token);
          this.settingsForm.has_imgbb_api_key = Boolean(s.has_imgbb_api_key);
          this.settingsForm.has_gemini_api_key = Boolean(s.has_gemini_api_key);
          this.settingsForm.has_google_client_secret = Boolean(s.has_google_client_secret);

          // Keep token inputs clean so placeholders show saved status
          this.settingsForm.fb_page_access_token = '';
          this.settingsForm.imgbb_api_key = '';
          this.settingsForm.gemini_api_key = '';
          this.settingsForm.google_client_secret = '';
          this.settingsForm.app_password = '';

          this.metaExchange.app_id = '2039281703363967';
          this.testIntegrations();
        }
      } catch (e) {}
    },
    async testIntegrations() {
      this.isTesting = true;
      try {
        const payload = {
          fb_page_id: this.settingsForm.fb_page_id
        };
        if (this.settingsForm.fb_page_access_token && !this.settingsForm.fb_page_access_token.includes('...')) {
          payload.fb_page_access_token = this.settingsForm.fb_page_access_token;
        }
        if (this.settingsForm.ig_business_account_id) {
          payload.ig_business_account_id = this.settingsForm.ig_business_account_id;
        }
        const res = await this.authFetch('/api/settings/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
          if (data.facebook) this.metaStatus.facebook = data.facebook;
          if (data.instagram) this.metaStatus.instagram = data.instagram;
        }
      } catch (e) {}
      finally {
        this.isTesting = false;
      }
    },
    
    // ── GOOGLE AUTH & INTEGRATION METHODS ──
    async connectGoogle() {
      if (!this.settingsForm.google_client_id && !this.settingsForm.google_client_secret) {
        this.showToast('Vui lòng nhập Google OAuth Client ID và Client Secret trước khi liên kết.', 'warning');
        return;
      }
      try {
        await this.saveSettings();
        const res = await this.authFetch('/api/google/auth-url');
        const data = await res.json();
        const redirectUrl = data.auth_url || data.url;
        if (res.ok && redirectUrl) {
          window.location.href = redirectUrl;
        } else {
          throw new Error(data.detail || 'Không thể lấy liên kết xác thực Google');
        }
      } catch (err) {
        this.showToast('Lỗi kết nối Google: ' + err.message, 'error');
      }
    },
    async testConnection() {
      await this.testIntegrations();
      this.showToast('Đã kiểm tra kết nối các kênh!', 'info');
    },

    async convertPermanentToken() {
      if (!this.metaExchange.short_token || !this.metaExchange.app_secret) {
        this.showToast('Vui lòng nhập App Secret và chuỗi Token ngắn hạn.', 'warning');
        return;
      }
      this.isConvertingToken = true;
      try {
        const res = await this.authFetch('/api/meta/exchange-permanent-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            app_id: this.metaExchange.app_id,
            app_secret: this.metaExchange.app_secret,
            short_token: this.metaExchange.short_token
          })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast(`🎉 Đã kích hoạt Token vĩnh viễn cho trang "${data.page_name}"!`, 'success');
          this.loadSettings();
          this.metaExchange.short_token = '';
        } else {
          throw new Error(data.detail || 'Lỗi chuyển đổi token');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.isConvertingToken = false;
      }
    },
    async saveSettings() {
      this.isSaving = true;
      try {
        const payload = {
          fb_page_id: this.settingsForm.fb_page_id,
          ig_business_account_id: this.settingsForm.ig_business_account_id,
          google_client_id: this.settingsForm.google_client_id,
          gemini_model: this.settingsForm.gemini_model,
        };

        if (this.settingsForm.fb_page_access_token && !this.settingsForm.fb_page_access_token.includes('...')) {
          payload.fb_page_access_token = this.settingsForm.fb_page_access_token.trim();
        }
        if (this.settingsForm.imgbb_api_key && !this.settingsForm.imgbb_api_key.includes('...')) {
          payload.imgbb_api_key = this.settingsForm.imgbb_api_key.trim();
        }
        if (this.settingsForm.gemini_api_key && !this.settingsForm.gemini_api_key.includes('...')) {
          payload.gemini_api_key = this.settingsForm.gemini_api_key.trim();
        }
        if (this.settingsForm.google_client_secret && !this.settingsForm.google_client_secret.includes('...')) {
          payload.google_client_secret = this.settingsForm.google_client_secret.trim();
        }
        if (this.settingsForm.app_password && this.settingsForm.app_password.trim()) {
          payload.app_password = this.settingsForm.app_password.trim();
        }

        const res = await this.authFetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.showToast('✅ Đã lưu cài đặt an toàn thành công!', 'success');
          this.loadSettings();
        } else {
          throw new Error(data.detail || 'Lỗi lưu cài đặt');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.isSaving = false;
      }
    },

    // ── AI ASSISTANT METHODS ──
    openAiModal() {
      this.aiModal.show = true;
      this.aiModal.result = null;
    },
    closeAiModal() {
      this.aiModal.show = false;
      this.aiModal.result = null;
    },
    async runAiCaptionGen() {
      this.aiModal.isLoading = true;
      try {
        const res = await this.authFetch('/api/ai/generate-caption', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            images: this.postForm.images,
            user_hint: this.aiModal.userHint
          })
        });
        const data = await res.json();
        if (res.ok && data.captions) {
          this.aiModal.result = data.captions;
        } else {
          throw new Error(data.detail || 'Lỗi gọi AI');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.aiModal.isLoading = false;
      }
    },
    applyAiCaption(cap, platform) {
      if (platform === 'fb') {
        this.postForm.fb_caption = cap;
        this.captionTab = 'fb';
      } else if (platform === 'ig') {
        this.postForm.ig_caption = cap;
        this.captionTab = 'ig';
      } else {
        this.postForm.google_caption = cap;
        this.captionTab = 'google';
      }
      this.closeAiModal();
      this.showToast('Đã áp dụng nội dung AI!', 'success');
    },

    // ── ROOTS CATALOG METHODS ──
    async loadRootsCategories() {
      try {
        const res = await this.authFetch('/api/roots/categories');
        const data = await res.json();
        if (res.ok && data.categories) {
          this.rootsCategories = data.categories;
        }
      } catch (e) {}
    },
    async loadRootsData() {
      this.isLoadingRoots = true;
      try {
        let endpoint = `/api/roots/products?page=${this.rootsPagination.current_page}&page_size=20`;
        if (this.rootsSearchQuery) {
          endpoint += `&search=${encodeURIComponent(this.rootsSearchQuery)}`;
        }
        if (this.selectedRootsCategory && this.selectedRootsCategory !== 'all') {
          endpoint += `&category=${encodeURIComponent(this.selectedRootsCategory)}`;
        }
        if (this.isFlashSaleOnly) {
          endpoint = `/api/roots/flash-sale?page=${this.rootsPagination.current_page}&page_size=20`;
        }

        const res = await this.authFetch(endpoint);
        const data = await res.json();
        if (res.ok && data.status === 'success') {
          this.rootsProducts = data.data || [];
          if (data.pagination) {
            this.rootsPagination = data.pagination;
          }
        }
      } catch (err) {
        console.error('Error loading roots data:', err);
      } finally {
        this.isLoadingRoots = false;
      }
    },
    changeRootsCategory(cat) {
      this.selectedRootsCategory = cat;
      this.rootsPagination.current_page = 1;
      this.loadRootsData();
    },
    handleRootsSearch() {
      this.rootsPagination.current_page = 1;
      this.loadRootsData();
    },
    toggleFlashSaleFilter() {
      this.isFlashSaleOnly = !this.isFlashSaleOnly;
      this.rootsPagination.current_page = 1;
      this.loadRootsData();
    },
    resetRootsFilters() {
      this.selectedRootsCategory = 'all';
      this.rootsSearchQuery = '';
      this.isFlashSaleOnly = false;
      this.rootsPagination.current_page = 1;
      this.loadRootsData();
    },
    changeRootsPage(p) {
      if (p < 1 || p > this.rootsPagination.total_pages) return;
      this.rootsPagination.current_page = p;
      this.loadRootsData();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },
    getRootsImageUrl(img) {
      if (!img) return 'https://roots.vn/themes/roots/assets/images/no-image.png';
      if (img.startsWith('http://') || img.startsWith('https://')) return img;
      return `https://img.roots.vn/products/${img.split('?')[0]}`;
    },
    getRootsProductUrl(p) {
      if (!p) return 'https://roots.vn';
      if (p.Slug) {
        if (p.DanhMucSlug) return `https://roots.vn/danh-muc/${p.DanhMucSlug}/${p.Slug}`;
        return `https://roots.vn/danh-muc/${p.Slug}`;
      }
      return 'https://roots.vn';
    },
    formatRootsPrice(val) {
      const num = parseFloat(val || 0);
      if (num <= 0) return 'Liên hệ';
      return num.toLocaleString('vi-VN') + 'đ';
    },
    hasDiscount(p) {
      const gKm = parseFloat(p.GiaSauKm || 0);
      const gOld = parseFloat(p.GiaTruocKm || 0);
      return gOld > gKm && gKm > 0;
    },
    
    // ── TEMPLATE HELPER SHORTCUTS ──
    getFbName() {
      return this.metaStatus.facebook.page_name || 'ROOTS - Organic Store & Juice Bar';
    },
    getFbPic() {
      return this.metaStatus.facebook.picture || this.metaStatus.instagram.profile_picture || '';
    },
    getIgName() {
      return this.metaStatus.instagram.username || 'rootsvn.official';
    },
    getIgPic() {
      return this.metaStatus.instagram.profile_picture || this.metaStatus.facebook.picture || '';
    },
    getBrandName() {
      return this.metaStatus.facebook.page_name || (this.metaStatus.instagram.username ? '@' + this.metaStatus.instagram.username : 'ROOTS - Organic Store & Juice Bar');
    },
    getBrandPic() {
      return this.metaStatus.facebook.picture || this.metaStatus.instagram.profile_picture || '';
    },
    downloadStoryImage() {
      if (!this.postForm.story_image) return;
      const url = this.getMediaUrl(this.postForm.story_image);
      const a = document.createElement('a');
      a.href = url;
      a.download = `story_roots_${Date.now()}.jpg`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      this.showToast('Đang tải ảnh Story 9:16 về máy...', 'success');
    },
    formatDateTime(dateStr) {
      return this.formatDate(dateStr);
    },
    deletePostItem(id) {
      return this.deletePost(id);
    },
    publishNow(id) {
      return this.publishPostNow(id);
    },
    showErrorModal(err) {
      return this.showErrorDetails(err);
    },
    exportStudioImage() {
      return this.exportAndApplyStory();
    },
    setStoryTemplate(tpl) {
      this.postForm.story_template = tpl;
      if (this.studioModal.show) this.applyStudioTemplate(tpl);
    },
    renderStudioSafeZone() {
      this.toggleSafeZone();
    },
    selectRootsCategory(cat) {
      this.changeRootsCategory(cat);
    },
    loadRootsProducts() {
      this.loadRootsData();
    },
    truncate(str, max = 50) {
      if (!str) return '';
      return str.length > max ? str.slice(0, max) + '...' : str;
    },

    calcDiscountPercent(p) {
      const gKm = parseFloat(p.GiaSauKm || 0);
      const gOld = parseFloat(p.GiaTruocKm || 0);
      if (gOld <= gKm || gOld <= 0) return 0;
      return Math.round(((gOld - gKm) / gOld) * 100);
    },

    // ── MULTI-PRODUCT COMBO & AI PROMPTS ──
    toggleSelectComboProduct(product) {
      const pId = product.id || product.MaNoiBo;
      const idx = this.selectedComboProducts.findIndex(p => (p.id || p.MaNoiBo) === pId);
      if (idx >= 0) {
        this.selectedComboProducts.splice(idx, 1);
      } else {
        if (this.selectedComboProducts.length >= 8) {
          this.showToast('Mỗi combo nên chọn tối đa 8 sản phẩm để đảm bảo thẩm mỹ tốt nhất', 'warning');
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
    openComboCampaignModal() {
      if (this.selectedComboProducts.length === 0) {
        this.showToast('Vui lòng chọn ít nhất 1 sản phẩm vào combo', 'warning');
        return;
      }
      this.comboModal.show = true;
      this.comboModal.result = null;
      this.comboModal.activeCaptionTab = 'fb';
      this.runComboCampaignGen();
    },
    closeComboCampaignModal() {
      this.comboModal.show = false;
    },
    async runComboCampaignGen() {
      this.comboModal.isLoading = true;
      try {
        const res = await this.authFetch('/api/roots/combo-generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            products: this.selectedComboProducts,
            user_hint: this.comboModal.userHint
          })
        });
        const data = await res.json();
        if (res.ok && data.data) {
          this.comboModal.result = data.data;
        } else {
          throw new Error(data.detail || 'Lỗi tạo chiến dịch combo');
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        this.comboModal.isLoading = false;
      }
    },
    async copyPromptToClipboard(promptText, idx) {
      try {
        await navigator.clipboard.writeText(promptText);
        this.comboModal.copiedPromptIdx = idx;
        this.showToast('📋 Đã sao chép Prompt vào bộ nhớ tạm!', 'success');
        setTimeout(() => {
          if (this.comboModal.copiedPromptIdx === idx) {
            this.comboModal.copiedPromptIdx = null;
          }
        }, 2500);
      } catch (err) {
        const textarea = document.createElement('textarea');
        textarea.value = promptText;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        textarea.remove();
        this.comboModal.copiedPromptIdx = idx;
        this.showToast('📋 Đã sao chép Prompt!', 'success');
      }
    },
    applyComboToComposer() {
      if (!this.comboModal.result) return;
      const d = this.comboModal.result;
      this.postForm.fb_caption = d.fb_caption || '';
      this.postForm.ig_caption = d.ig_caption || '';
      this.postForm.google_caption = d.google_caption || '';
      this.postForm.story_hook = d.story_hook || '';
      this.postForm.target_fb = true;
      this.postForm.target_ig = true;
      this.postForm.target_story = true;
      this.postForm.target_google = Boolean(this.settingsForm.google_connected && this.settingsForm.google_location_id);
      this.postForm.google_action_type = 'ORDER';
      this.postForm.google_action_url = 'https://roots.vn';
      this.comboModal.show = false;
      this.activeTab = 'composer';
      this.showToast('✨ Đã nạp nội dung Combo vào khung Tạo bài! Hãy tải các ảnh bạn vừa tạo lên.', 'success');
    },
    async downloadProductFile(imgUrlOrName, productName) {
      if (!imgUrlOrName) return;
      try {
        const url = `/api/roots/download-product-image?img=${encodeURIComponent(imgUrlOrName)}&name=${encodeURIComponent(productName || 'product')}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        
        let ext = '.webp';
        const lowerImg = imgUrlOrName.toLowerCase();
        if (lowerImg.includes('.jpg') || lowerImg.includes('.jpeg')) ext = '.jpg';
        else if (lowerImg.includes('.png')) ext = '.png';
        
        const safeName = (productName || 'product').replace(/[/\\?%*:|"<>]/g, '-').trim();
        a.download = safeName.toLowerCase().endsWith(ext) ? safeName : safeName + ext;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => window.URL.revokeObjectURL(blobUrl), 2000);
        this.showToast(`📥 Đã tải về: ${this.truncate(productName, 30)}`, 'success');
      } catch (err) {
        console.error('Download error:', err);
        // Fallback: direct CDN link
        const directUrl = imgUrlOrName.startsWith('http') ? imgUrlOrName : `https://img.roots.vn/products/${imgUrlOrName}`;
        window.open(directUrl, '_blank');
        this.showToast(`Mở ảnh gốc trên tab mới: ${this.truncate(productName, 25)}`, 'warning');
      }
    },
    async downloadAllComboImages() {
      if (!this.selectedComboProducts || this.selectedComboProducts.length === 0) return;
      this.showToast(`📥 Bắt đầu tải toàn bộ ${this.selectedComboProducts.length} ảnh sản phẩm...`, 'success');
      for (let i = 0; i < this.selectedComboProducts.length; i++) {
        const p = this.selectedComboProducts[i];
        await this.downloadProductFile(p.AnhSanPham, p.TenSanPham);
        if (i < this.selectedComboProducts.length - 1) {
          await new Promise(r => setTimeout(r, 400));
        }
      }
    }
  }
}).mount('#app');
