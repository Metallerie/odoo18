-- 🔄 Nettoyage précédent
DELETE FROM website_robots;

-- 🚀 Insertion des directives optimisées
INSERT INTO website_robots (content, create_uid, create_date, write_uid, write_date)
VALUES
-- Sitemaps
('Sitemap: https://www.metallerie.xyz/blog/metallerie-artisanale-corneilla-perpignan-1/feed', 1, now(), 1, now()),

-- Directives SEO recommandées
('Disallow: /search', 1, now(), 1, now()),
('Disallow: /login', 1, now(), 1, now()),
('Disallow: /register', 1, now(), 1, now()),
('Disallow: /cart', 1, now(), 1, now()),
('Disallow: /checkout', 1, now(), 1, now()),
('Disallow: /admin', 1, now(), 1, now()),
('Disallow: /*.pdf$', 1, now(), 1, now()),
('Crawl-delay: 10', 1, now(), 1, now()),


-- Disallow avancés (issus d’Odoo/SEO)
('Disallow: /my/*', 1, now(), 1, now()),
('Disallow: /*/my/*', 1, now(), 1, now()),
('Disallow: /groups/*', 1, now(), 1, now()),
('Disallow: */groups/*', 1, now(), 1, now()),
('Disallow: */typo?domain=', 1, now(), 1, now()),
('Disallow: *?*orderby=', 1, now(), 1, now()),
('Disallow: *?*order=', 1, now(), 1, now()),
('Disallow: */tag/*,*', 1, now(), 1, now()),
('Disallow: */page/*/*', 1, now(), 1, now()),
('Disallow: *?*page=', 1, now(), 1, now()),
('Disallow: *?*search=*', 1, now(), 1, now()),
('Disallow: ?*grade_id=*', 1, now(), 1, now()),
('Disallow: ?*country_id=*', 1, now(), 1, now()),
('Disallow: /im_livechat/init', 1, now(), 1, now()),
('Disallow: */google_map/*', 1, now(), 1, now()),
('Disallow: /calendar/view/*', 1, now(), 1, now()),
('Disallow: /event/*/exhibitor/*', 1, now(), 1, now()),
('Disallow: */page/website_event.*', 1, now(), 1, now()),
('Disallow: */website-page-fake-*', 1, now(), 1, now()),
('Disallow: */forum/*/user/*', 1, now(), 1, now()),
('Disallow: */forum/user/*', 1, now(), 1, now()),
('Disallow: */forum/*/tag/*', 1, now(), 1, now()),
('Disallow: */_activate_your_database/*', 1, now(), 1, now()),
('Disallow: */country_flags/*', 1, now(), 1, now()),
('Disallow: */web/image/res.lang/*', 1, now(), 1, now()),
('Disallow: */web/image/res.partner/*', 1, now(), 1, now()),
('Disallow: */web/image/res.users/*', 1, now(), 1, now()),
('Disallow: */web/login*', 1, now(), 1, now()),
('Disallow: */web/reset_password*', 1, now(), 1, now()),
('Disallow: */web/signup*', 1, now(), 1, now()),
('Disallow: *?selected_app=*', 1, now(), 1, now()),
('Disallow: /profile/avatar/*', 1, now(), 1, now()),
('Disallow: */profile/users*', 1, now(), 1, now()),
('Disallow: /profile/ranks_badges?*forum_origin=*', 1, now(), 1, now()),
('Disallow: /jobs?*', 1, now(), 1, now()),
('Disallow: /jobs/apply/*', 1, now(), 1, now()),
('Disallow: /web?*', 1, now(), 1, now()),
('Disallow: /appointment*?*domain=*', 1, now(), 1, now()),
('Disallow: /appointment/*?timezone*', 1, now(), 1, now()),
('Disallow: /customers?tag_id*', 1, now(), 1, now()),
('Disallow: /event?*', 1, now(), 1, now()),
('Disallow: /event/*?*tags=', 1, now(), 1, now()),
('Disallow: /event/*/ics/*', 1, now(), 1, now()),
('Disallow: /event/page/*', 1, now(), 1, now()),
('Disallow: /forum/*?*filters*', 1, now(), 1, now()),
('Disallow: /forum/*?*sorting*', 1, now(), 1, now()),
('Disallow: /forum/*/tag/*/questions*', 1, now(), 1, now()),
('Disallow: /accounting-firms/country/*?grade*', 1, now(), 1, now());
