import { Component, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
import { BreakpointObserver, Breakpoints } from '@angular/cdk/layout';
import { distinctUntilChanged, tap } from 'rxjs/operators';
import { MatSidenav } from '@angular/material/sidenav';
import AppDataService from './shared/services/app-data.service';


@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent {
  title = 'trisonics-scouting-ng17';

  @ViewChild('sidenav', { static: true })
  public sidenav!: MatSidenav;

  public teamKeyVisible: boolean = false;

  public fullDisplay: boolean = true;

  public sidenavOpen: boolean = false

  private defaultMediaQuery = '(min-width: 800px)';

  private readonly breakpoint$ = this.breakpointObserver.observe(
    [Breakpoints.Large, Breakpoints.Medium, Breakpoints.Small, Breakpoints.XSmall,
      Breakpoints.Tablet, this.defaultMediaQuery]
  ).pipe(
    tap(value => console.log(value)),
    distinctUntilChanged()
  );

  constructor(
    public appData: AppDataService,
    public media: BreakpointObserver,
    public breakpointObserver: BreakpointObserver,
    public router: Router,
  ) { }

  public checkSettingsValid(): void {
    if (this.appData.teamKey.length == 0
        ||
        this.appData.scouterName.length == 0
        ||
        this.appData.eventKey.length == 0
    ) {
      this.goToSettings();
    }
  }

  public ngOnInit(): void {
    this.checkSettingsValid();
    this.breakpoint$.subscribe(() => {
      console.log('something');
      this.fullDisplay = false;
      if (this.breakpointObserver.isMatched(this.defaultMediaQuery)) {
        this.fullDisplay = true;
      }
      if (this.breakpointObserver.isMatched(Breakpoints.Large)) {
        this.fullDisplay = true;
      }
      if (this.breakpointObserver.isMatched(Breakpoints.Medium)) {
        this.fullDisplay = true;
      }
      if (this.breakpointObserver.isMatched(Breakpoints.Tablet)) {
        this.fullDisplay = true;
      }
      if (this.breakpointObserver.isMatched(Breakpoints.Small)) {
        this.fullDisplay = false;
      }
      if (this.breakpointObserver.isMatched(Breakpoints.XSmall)) {
        this.fullDisplay = false;
      }
      if (this.fullDisplay) {
        this.sidenavOpen = false;
      }
    });
  }

  public sidenavClick(): void {
    if (this.sidenav.mode !== 'side') {
      this.sidenav.close();
      this.sidenavOpen = false;
    }
  }

 public displaySidenavMenu(): void {
  this.sidenav.toggle();
 }

  public enableDisplayTeamKey(): void {
    this.teamKeyVisible = true;
    setTimeout(() => {
      this.teamKeyVisible = false;
    }, 5000);
  }

  get displayTeamKey(): string {
    if (this.teamKeyVisible) {
      return this.appData.teamKey;
    }
    if (this.appData.teamKey) {
      return '********';
    }

    return 'none set!';
  }

  public goToSettings(): void {
    this.router.navigate(['/settings'])
  }
}
